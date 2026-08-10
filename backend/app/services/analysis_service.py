"""Application service for analysis jobs.

Sits between the HTTP layer and the pipeline: validates uploads, persists the
recording, creates the job row, and maps ORM records onto API schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import IO

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.constants import AnalysisStatus
from app.core.exceptions import NotFoundError, PayloadTooLargeError, UnsupportedMediaError
from app.core.logging import get_logger
from app.db.models import Analysis
from app.db.repository import AnalysisRepository
from app.schemas.analysis import AnalysisDetail, AnalysisSummary
from app.schemas.report import AgentTrace, AnalysisEvidence, ScamReport
from app.schemas.transcript import Transcript
from app.services.storage import StorageBackend, get_storage

logger = get_logger(__name__)


class AnalysisService:
    """Create, read and delete analyses."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._storage = storage or get_storage()
        self._repository = AnalysisRepository(session)

    # ---- Validation -------------------------------------------------------
    def _validate_upload(self, filename: str, size_bytes: int) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix not in self._settings.allowed_audio_extensions:
            allowed = ", ".join(sorted(self._settings.allowed_audio_extensions))
            raise UnsupportedMediaError(
                f"'{suffix or filename}' is not a supported audio format. Allowed: {allowed}"
            )
        if size_bytes <= 0:
            raise UnsupportedMediaError("The uploaded file is empty.")
        if size_bytes > self._settings.max_upload_bytes:
            raise PayloadTooLargeError(
                f"File is {size_bytes / 1_048_576:.1f} MB; the limit is "
                f"{self._settings.max_upload_mb} MB."
            )
        return suffix

    # ---- Commands ---------------------------------------------------------
    async def create_from_upload(
        self, *, filename: str, content_type: str | None, size_bytes: int, stream: IO[bytes]
    ) -> Analysis:
        """Validate, store the audio, and create a pending job."""
        suffix = self._validate_upload(filename, size_bytes)
        storage_key = f"{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}{suffix}"
        await self._storage.save(storage_key, stream)

        analysis = await self._repository.create(
            filename=filename,
            content_type=content_type,
            storage_key=storage_key,
            size_bytes=size_bytes,
            status=AnalysisStatus.PENDING,
        )
        await self._commit_job(analysis)
        logger.info("analysis_created", analysis_id=analysis.id, filename=filename, source="audio")
        return analysis

    async def create_from_text(self, *, filename: str, size_bytes: int) -> Analysis:
        """Create a job for a directly submitted transcript (no audio stored)."""
        analysis = await self._repository.create(
            filename=filename,
            content_type="text/plain",
            storage_key=None,
            size_bytes=size_bytes,
            status=AnalysisStatus.PENDING,
        )
        await self._commit_job(analysis)
        logger.info("analysis_created", analysis_id=analysis.id, filename=filename, source="text")
        return analysis

    async def _commit_job(self, analysis: Analysis) -> None:
        """Make the job row durable before a background worker is told about it.

        The pipeline runs in a different session on a different connection. If
        the insert were still uncommitted when the task started, the worker
        would not find the row and the job would sit at 'pending' forever.
        """
        await self._session.commit()
        await self._session.refresh(analysis)

    async def delete(self, analysis_id: str) -> None:
        analysis = await self._repository.get(analysis_id)
        if analysis is None:
            raise NotFoundError(f"Analysis {analysis_id} not found")
        if analysis.storage_key:
            try:
                await self._storage.delete(analysis.storage_key)
            except Exception as exc:  # the row must go even if the blob will not
                logger.warning(
                    "stored_audio_delete_failed", key=analysis.storage_key, error=str(exc)
                )
        await self._repository.delete(analysis_id)

    # ---- Queries ----------------------------------------------------------
    async def get_detail(self, analysis_id: str) -> AnalysisDetail:
        analysis = await self._repository.get(analysis_id)
        if analysis is None:
            raise NotFoundError(f"Analysis {analysis_id} not found")
        return self.to_detail(analysis)

    async def list(
        self, *, limit: int = 20, offset: int = 0, status: AnalysisStatus | None = None
    ) -> tuple[list[AnalysisSummary], int]:
        rows, total = await self._repository.list(limit=limit, offset=offset, status=status)
        return [self.to_summary(row) for row in rows], total

    # ---- Mapping ----------------------------------------------------------
    @staticmethod
    def to_summary(analysis: Analysis) -> AnalysisSummary:
        return AnalysisSummary(
            id=analysis.id,
            filename=analysis.filename,
            status=AnalysisStatus(analysis.status),
            risk_score=analysis.risk_score,
            risk_level=analysis.risk_level,
            verdict=analysis.verdict,
            duration_seconds=analysis.duration_seconds,
            created_at=analysis.created_at,
            completed_at=analysis.completed_at,
        )

    @staticmethod
    def to_detail(analysis: Analysis) -> AnalysisDetail:
        return AnalysisDetail(
            **AnalysisService.to_summary(analysis).model_dump(),
            language=analysis.language,
            error=analysis.error,
            processing_seconds=analysis.processing_seconds,
            transcript=Transcript.model_validate(analysis.transcript)
            if analysis.transcript
            else None,
            evidence=AnalysisEvidence.model_validate(analysis.evidence)
            if analysis.evidence
            else None,
            report=ScamReport.model_validate(analysis.report) if analysis.report else None,
            traces=[AgentTrace.model_validate(trace) for trace in (analysis.traces or [])],
        )
