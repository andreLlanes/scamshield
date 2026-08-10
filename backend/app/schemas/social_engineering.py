"""Agent 4 output — psychological manipulation tactics found in the call."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.constants import TACTIC_DESCRIPTIONS, TACTIC_LABELS, TacticType


class TacticEvidence(BaseModel):
    """One quoted line that demonstrates a tactic."""

    quote: str
    timestamp: str | None = None
    explanation: str = ""


class TacticDetection(BaseModel):
    """A detected tactic together with everything that supports it."""

    tactic: TacticType
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    severity: float = Field(
        default=0.5, ge=0.0, le=1.0, description="How aggressively the tactic was used."
    )
    evidence: list[TacticEvidence] = Field(default_factory=list)

    @property
    def label(self) -> str:
        return TACTIC_LABELS[self.tactic]

    @property
    def description(self) -> str:
        return TACTIC_DESCRIPTIONS[self.tactic]


class SocialEngineeringResult(BaseModel):
    """Aggregate view of the manipulation profile of the call."""

    tactics: list[TacticDetection] = Field(default_factory=list)
    summary: str = ""
    manipulation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_fallback: bool = Field(
        default=False, description="True when the lexicon analyzer ran instead of the LLM."
    )

    @property
    def detected_tactics(self) -> list[TacticType]:
        return [detection.tactic for detection in self.tactics]

    @classmethod
    def score_from(cls, tactics: list[TacticDetection]) -> float:
        """Combine per-tactic strengths into a single 0-1 manipulation score.

        Uses a saturating sum rather than an average: five weak tactics is a
        worse sign than one strong one, but ten tactics is not twice as bad as
        five, so each additional tactic contributes less than the last.
        """
        if not tactics:
            return 0.0
        strengths = sorted(
            (detection.confidence * detection.severity for detection in tactics), reverse=True
        )
        score = 0.0
        remaining = 1.0
        for strength in strengths:
            score += remaining * strength
            remaining = 1.0 - score
            if remaining <= 0.01:
                break
        return round(min(score, 1.0), 4)
