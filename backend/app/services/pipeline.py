"""The end-to-end analysis pipeline.

Upload → Whisper (Agent 1) → Orchestrator (Agents 2-5) → persisted report.

Runs as a background task so the HTTP request returns immediately; the client
polls the analysis resource for status. A semaphore caps concurrent jobs because
Whisper weights and an LLM in the same process do not share a machine politely.
"""

from __future__ import annotations

import time
from pathlib import Path

import anyio

from app.agents.orchestrator import Orchestrator
from app.core.config import Settings, get_settings
from app.core.constants import AnalysisStatus
from app.core.logging import get_logger
from app.db.repository import AnalysisRepository
from app.db.session import session_scope
from app.ml.transcription.service import TranscriptionService, get_transcription_service
from app.schemas.transcript import Transcript
from app.services.storage import StorageBackend, get_storage

logger = get_logger(__name__)


class AnalysisPipeline:
    """Drives one recording from upload to finished report."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transcriber: TranscriptionService | None = None,
        orchestrator: Orchestrator | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transcriber = transcriber or get_transcription_service()
        self._orchestrator = orchestrator or Orchestrator(settings=self._settings)
        self._storage = storage or get_storage()
        self._semaphore = anyio.Semaphore(self._settings.max_concurrent_analyses)

    # ---- Status helpers ---------------------------------------------------
    @staticmethod
    async def _set_status(
        analysis_id: str, status: AnalysisStatus, error: str | None = None
    ) -> None:
        async with session_scope() as session:
            await AnalysisRepository(session).set_status(analysis_id, status, error=error)

    # ---- Entry points -----------------------------------------------------
    async def run_from_audio(self, analysis_id: str, storage_key: str) -> None:
        """Transcribe a stored recording, then analyse it."""
        async with self._semaphore:
            started = time.perf_counter()
            try:
                await self._set_status(analysis_id, AnalysisStatus.TRANSCRIBING)
                audio_path: Path = await self._storage.local_path(storage_key)
                transcript = await self._transcriber.transcribe(audio_path)

                async with session_scope() as session:
                    await AnalysisRepository(session).update(
                        analysis_id,
                        transcript=transcript.model_dump(),
                        language=transcript.language,
                        duration_seconds=transcript.duration_seconds,
                        status=AnalysisStatus.ANALYZING,
                    )

                await self._analyze(analysis_id, transcript, started)
            except Exception as exc:
                await self._fail(analysis_id, exc)

    async def run_from_transcript(self, analysis_id: str, transcript: Transcript) -> None:
        """Analyse a transcript supplied directly, skipping Agent 1."""
        async with self._semaphore:
            started = time.perf_counter()
            try:
                async with session_scope() as session:
                    await AnalysisRepository(session).update(
                        analysis_id,
                        transcript=transcript.model_dump(),
                        language=transcript.language,
                        duration_seconds=transcript.duration_seconds,
                        status=AnalysisStatus.ANALYZING,
                    )
                await self._analyze(analysis_id, transcript, started)
            except Exception as exc:
                await self._fail(analysis_id, exc)

    # ---- Core -------------------------------------------------------------
    async def _analyze(self, analysis_id: str, transcript: Transcript, started: float) -> None:
        result = await self._orchestrator.analyze(transcript)
        elapsed = round(time.perf_counter() - started, 3)

        async with session_scope() as session:
            repository = AnalysisRepository(session)
            await repository.update(
                analysis_id,
                evidence=result.evidence.model_dump(),
                report=result.report.model_dump(mode="json"),
                risk_score=result.report.risk.score,
                risk_level=result.report.risk.level.value,
                verdict=result.report.verdict,
                traces=[trace.model_dump() for trace in result.traces],
                processing_seconds=elapsed,
            )
            await repository.set_status(analysis_id, AnalysisStatus.COMPLETED)

        logger.info(
            "analysis_completed",
            analysis_id=analysis_id,
            risk_score=result.report.risk.score,
            seconds=elapsed,
            used_llm=result.used_llm,
        )

    async def _fail(self, analysis_id: str, exc: Exception) -> None:
        message = getattr(exc, "message", None) or str(exc)
        logger.error("analysis_failed", analysis_id=analysis_id, error=message, exc_info=exc)
        try:
            await self._set_status(analysis_id, AnalysisStatus.FAILED, error=message[:2000])
        except Exception:  # pragma: no cover - the DB is already unhappy
            logger.exception("analysis_failure_not_recorded", analysis_id=analysis_id)


_pipeline: AnalysisPipeline | None = None


def get_pipeline() -> AnalysisPipeline:
    """Process-wide pipeline (holds the model handles and the job semaphore)."""
    global _pipeline
    if _pipeline is None:
        _pipeline = AnalysisPipeline()
    return _pipeline
