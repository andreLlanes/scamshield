"""Agent 5 output — the explainable scam assessment report."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.constants import RiskLevel, ScamCategory
from app.schemas.classification import ClassificationResult
from app.schemas.factcheck import FactCheckResult
from app.schemas.social_engineering import SocialEngineeringResult


class EvidenceWeight(BaseModel):
    """How much one agent contributed to the final score, and why."""

    source: str = Field(..., description="classifier | social_engineering | fact_check")
    label: str
    raw_score: float = Field(..., ge=0.0, le=1.0, description="The agent's own 0-1 signal.")
    weight: float = Field(..., ge=0.0, le=1.0, description="Weight applied to that signal.")
    weighted_points: float = Field(..., description="Points contributed to the 0-100 risk score.")
    rationale: str = ""


class RiskBreakdown(BaseModel):
    """The arithmetic behind the headline number, exposed for explainability."""

    score: float = Field(..., ge=0.0, le=100.0)
    level: RiskLevel
    components: list[EvidenceWeight] = Field(default_factory=list)


class RedFlag(BaseModel):
    """A single concrete warning sign, cited back to the recording."""

    title: str
    detail: str
    severity: RiskLevel = RiskLevel.MEDIUM
    quote: str | None = None
    timestamp: str | None = None
    source_agent: str = "orchestrator"


class ScamReport(BaseModel):
    """The user-facing deliverable: a verdict plus the reasoning behind it."""

    verdict: str = Field(
        ..., description="One-line headline, e.g. 'Likely bank impersonation scam'."
    )
    risk: RiskBreakdown
    category: ScamCategory = ScamCategory.UNKNOWN
    summary: str = Field(default="", description="Two to four sentence plain-language explanation.")
    red_flags: list[RedFlag] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    caller_claims: list[str] = Field(default_factory=list)
    is_fallback: bool = Field(
        default=False, description="True when the report was assembled without an LLM."
    )


class AnalysisEvidence(BaseModel):
    """Every intermediate agent output, kept so the report stays auditable."""

    classification: ClassificationResult | None = None
    fact_check: FactCheckResult | None = None
    social_engineering: SocialEngineeringResult | None = None


class AgentTrace(BaseModel):
    """Per-agent execution record, surfaced in the UI as the 'agent timeline'."""

    agent: str
    status: str = Field(default="completed", description="completed | skipped | failed")
    started_at: float = Field(default=0.0, description="Monotonic start offset in seconds.")
    duration_seconds: float = 0.0
    detail: str = ""
