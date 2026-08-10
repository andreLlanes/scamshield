"""Domain constants shared across agents.

Keeping the vocabulary in one place means the ML classifier, the social
engineering agent, the report generator and the frontend all speak about the
same tactics and the same risk bands.
"""

from __future__ import annotations

from enum import StrEnum


class AnalysisStatus(StrEnum):
    """Lifecycle of a single uploaded recording."""

    PENDING = "pending"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(StrEnum):
    """Bucketed verdict shown to the user."""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TacticType(StrEnum):
    """The eight psychological tactics ScamShield reports on."""

    AUTHORITY = "authority"
    URGENCY = "urgency"
    FEAR = "fear"
    SCARCITY = "scarcity"
    TRUST = "trust"
    PRESSURE = "pressure"
    REWARD = "reward"
    ISOLATION = "isolation"


class ClaimVerdict(StrEnum):
    """Outcome of verifying one factual claim against the knowledge base."""

    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    UNVERIFIED = "unverified"


class ScamCategory(StrEnum):
    """Coarse taxonomy used for the headline label on the report."""

    BANK_IMPERSONATION = "bank_impersonation"
    GOVERNMENT_IMPERSONATION = "government_impersonation"
    TECH_SUPPORT = "tech_support"
    PRIZE_LOTTERY = "prize_lottery"
    INVESTMENT = "investment"
    DELIVERY_PARCEL = "delivery_parcel"
    LOAN_OFFER = "loan_offer"
    FAMILY_EMERGENCY = "family_emergency"
    JOB_OFFER = "job_offer"
    UNKNOWN = "unknown"
    LEGITIMATE = "legitimate"


# Risk banding: lower bound (inclusive) of each band on a 0-100 scale.
RISK_THRESHOLDS: tuple[tuple[float, RiskLevel], ...] = (
    (85.0, RiskLevel.CRITICAL),
    (65.0, RiskLevel.HIGH),
    (40.0, RiskLevel.MEDIUM),
    (20.0, RiskLevel.LOW),
    (0.0, RiskLevel.SAFE),
)

TACTIC_LABELS: dict[TacticType, str] = {
    TacticType.AUTHORITY: "Authority",
    TacticType.URGENCY: "Urgency",
    TacticType.FEAR: "Fear",
    TacticType.SCARCITY: "Scarcity",
    TacticType.TRUST: "False Trust",
    TacticType.PRESSURE: "Pressure",
    TacticType.REWARD: "Reward",
    TacticType.ISOLATION: "Isolation",
}

TACTIC_DESCRIPTIONS: dict[TacticType, str] = {
    TacticType.AUTHORITY: (
        "The caller claims to represent a bank, government agency, or other institution "
        "in order to borrow its credibility."
    ),
    TacticType.URGENCY: (
        "The caller imposes an artificial deadline so you act before you can verify anything."
    ),
    TacticType.FEAR: (
        "The caller threatens arrest, account closure, legal action, or loss of money."
    ),
    TacticType.SCARCITY: (
        "The caller frames the offer as limited or one-time-only to discourage reflection."
    ),
    TacticType.TRUST: (
        "The caller name-drops personal details or fake reference numbers to appear legitimate."
    ),
    TacticType.PRESSURE: (
        "The caller refuses to let you hang up, call back, or consult someone else."
    ),
    TacticType.REWARD: (
        "The caller dangles a prize, refund, rebate, or guaranteed return as bait."
    ),
    TacticType.ISOLATION: (
        "The caller tells you to keep the call secret from family, staff, or the police."
    ),
}


def risk_level_for(score: float) -> RiskLevel:
    """Map a 0-100 risk score onto its :class:`RiskLevel` band."""
    for threshold, level in RISK_THRESHOLDS:
        if score >= threshold:
            return level
    return RiskLevel.SAFE
