"""Agent 3 output — RAG-backed verification of the caller's factual claims."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.constants import ClaimVerdict


class RetrievedDocument(BaseModel):
    """A knowledge-base chunk pulled back by the retriever."""

    doc_id: str
    title: str
    source: str = Field(default="internal", description="Where the document came from.")
    content: str
    score: float = Field(default=0.0, description="Similarity score; higher is closer.")


class FactualClaim(BaseModel):
    """A checkable assertion extracted from the transcript."""

    claim: str = Field(..., description="The claim as stated by the caller.")
    quote: str = Field(default="", description="Verbatim transcript snippet supporting the claim.")
    timestamp: str | None = Field(default=None, description="``mm:ss`` position in the recording.")
    category: str = Field(
        default="general",
        description="e.g. identity, procedure, payment, legal, offer.",
    )


class ClaimVerification(BaseModel):
    """A claim, judged against retrieved evidence."""

    claim: FactualClaim
    verdict: ClaimVerdict = ClaimVerdict.UNVERIFIED
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = Field(default="", description="Plain-language reasoning for the verdict.")
    evidence: list[RetrievedDocument] = Field(default_factory=list)


class FactCheckResult(BaseModel):
    """Everything the fact-verification agent concluded."""

    verifications: list[ClaimVerification] = Field(default_factory=list)
    summary: str = Field(default="")
    is_fallback: bool = Field(
        default=False, description="True when the deterministic checker ran instead of the LLM."
    )

    @property
    def contradicted_count(self) -> int:
        return sum(1 for v in self.verifications if v.verdict == ClaimVerdict.CONTRADICTED)

    @property
    def unverified_count(self) -> int:
        return sum(1 for v in self.verifications if v.verdict == ClaimVerdict.UNVERIFIED)

    @property
    def risk_contribution(self) -> float:
        """0-1 risk signal: contradicted claims weigh far more than unverifiable ones."""
        if not self.verifications:
            return 0.0
        total = len(self.verifications)
        score = (self.contradicted_count * 1.0 + self.unverified_count * 0.45) / total
        return round(min(score, 1.0), 4)
