"""API-facing request and response models for an analysis job."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import AnalysisStatus
from app.schemas.report import AgentTrace, AnalysisEvidence, ScamReport
from app.schemas.transcript import Transcript


class AnalysisCreateFromText(BaseModel):
    """Skip Agent 1 and analyse a transcript directly (handy for tests/demos)."""

    transcript: str = Field(..., min_length=10, max_length=50_000)
    language: str = Field(default="en", max_length=8)
    filename: str = Field(default="pasted-transcript.txt", max_length=255)


class AnalysisSummary(BaseModel):
    """Row shape for the history list."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    status: AnalysisStatus
    risk_score: float | None = None
    risk_level: str | None = None
    verdict: str | None = None
    duration_seconds: float | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AnalysisDetail(AnalysisSummary):
    """Full record including every agent's intermediate output."""

    language: str | None = None
    error: str | None = None
    processing_seconds: float | None = None
    transcript: Transcript | None = None
    evidence: AnalysisEvidence | None = None
    report: ScamReport | None = None
    traces: list[AgentTrace] = Field(default_factory=list)


class AnalysisListResponse(BaseModel):
    items: list[AnalysisSummary]
    total: int
    limit: int
    offset: int


class AnalysisAcceptedResponse(BaseModel):
    """Returned by the upload endpoint once the job is queued."""

    id: str
    status: AnalysisStatus
    filename: str
    poll_url: str


class HealthResponse(BaseModel):
    """Component-by-component readiness, used by the frontend status strip."""

    status: str
    version: str
    environment: str
    components: dict[str, ComponentHealth]


class ComponentHealth(BaseModel):
    ready: bool
    detail: str
    degraded_to: str | None = None


HealthResponse.model_rebuild()
