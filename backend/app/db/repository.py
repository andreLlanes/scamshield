"""Data access for analysis jobs.

The rest of the app talks to this repository instead of writing queries, so
the ORM stays contained to ``app.db``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AnalysisStatus
from app.core.exceptions import NotFoundError
from app.db.base import utcnow
from app.db.models import Analysis


class AnalysisRepository:
    """CRUD operations for :class:`~app.db.models.analysis.Analysis`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        filename: str,
        content_type: str | None = None,
        storage_key: str | None = None,
        size_bytes: int | None = None,
        status: AnalysisStatus = AnalysisStatus.PENDING,
    ) -> Analysis:
        analysis = Analysis(
            filename=filename,
            content_type=content_type,
            storage_key=storage_key,
            size_bytes=size_bytes,
            status=status,
        )
        self._session.add(analysis)
        await self._session.flush()
        return analysis

    async def get(self, analysis_id: str) -> Analysis | None:
        return await self._session.get(Analysis, analysis_id)

    async def list(
        self, *, limit: int = 20, offset: int = 0, status: AnalysisStatus | None = None
    ) -> tuple[list[Analysis], int]:
        stmt = select(Analysis).order_by(Analysis.created_at.desc())
        count_stmt = select(func.count()).select_from(Analysis)
        if status is not None:
            stmt = stmt.where(Analysis.status == status)
            count_stmt = count_stmt.where(Analysis.status == status)

        rows = (await self._session.execute(stmt.limit(limit).offset(offset))).scalars().all()
        total = (await self._session.execute(count_stmt)).scalar_one()
        return list(rows), int(total)

    async def set_status(
        self, analysis_id: str, status: AnalysisStatus, *, error: str | None = None
    ) -> Analysis:
        analysis = await self.get(analysis_id)
        if analysis is None:
            # Never silent: a status write that lands nowhere would strand the
            # job as 'pending' for the client with no trace of why.
            raise NotFoundError(f"Analysis {analysis_id} not found")
        analysis.status = status
        if error is not None:
            analysis.error = error
        if status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED):
            analysis.completed_at = utcnow()
        await self._session.flush()
        return analysis

    async def update(self, analysis_id: str, **fields: Any) -> Analysis:
        analysis = await self.get(analysis_id)
        if analysis is None:
            raise NotFoundError(f"Analysis {analysis_id} not found")
        for key, value in fields.items():
            if not hasattr(analysis, key):
                raise AttributeError(f"Analysis has no field {key!r}")
            setattr(analysis, key, value)
        await self._session.flush()
        return analysis

    async def delete(self, analysis_id: str) -> bool:
        analysis = await self.get(analysis_id)
        if analysis is None:
            return False
        await self._session.delete(analysis)
        return True
