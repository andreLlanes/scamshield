"""ORM model for an analysis job.

Agent outputs are stored as JSON blobs rather than exploded into tables: they
are read as a whole, versioned with the pipeline, and never queried field by
field. The columns that *are* promoted (status, risk score, verdict) are the
ones the history list filters and sorts on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import AnalysisStatus
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Analysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analyses"

    # ---- Input ------------------------------------------------------------
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128))
    storage_key: Mapped[str | None] = mapped_column(String(512))
    size_bytes: Mapped[int | None] = mapped_column()

    # ---- Lifecycle --------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(32), default=AnalysisStatus.PENDING, nullable=False, index=True
    )
    error: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_seconds: Mapped[float | None] = mapped_column(Float)

    # ---- Agent 1 ----------------------------------------------------------
    language: Mapped[str | None] = mapped_column(String(16))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    transcript: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # ---- Agents 2-4 (evidence) -------------------------------------------
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # ---- Agent 5 (report) -------------------------------------------------
    report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    risk_score: Mapped[float | None] = mapped_column(Float, index=True)
    risk_level: Mapped[str | None] = mapped_column(String(16))
    verdict: Mapped[str | None] = mapped_column(String(255))

    # ---- Observability ----------------------------------------------------
    traces: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)

    __table_args__ = (Index("ix_analyses_created_at_desc", "created_at"),)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Analysis id={self.id} status={self.status} risk={self.risk_score}>"
