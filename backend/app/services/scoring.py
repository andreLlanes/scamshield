"""Risk scoring — the arithmetic that turns three agent signals into one number.

Deliberately simple and deterministic. The LLM writes the *explanation*; it does
not get to choose the score, so two identical calls always score the same and
the breakdown shown to the user is the calculation that actually ran.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.constants import RiskLevel, ScamCategory, risk_level_for
from app.schemas.classification import ClassificationResult
from app.schemas.factcheck import FactCheckResult
from app.schemas.report import EvidenceWeight, RiskBreakdown
from app.schemas.social_engineering import SocialEngineeringResult

_LABELS = {
    "classifier": "ML scam classifier",
    "social_engineering": "Social engineering analysis",
    "fact_check": "Claim verification",
}

# A single contradicted claim of this kind is decisive on its own, so the score
# is floored rather than left to the weighted average to express.
_CRITICAL_FLOOR = 78.0


def _rationale(source: str, raw: float, evidence: object) -> str:
    if source == "classifier":
        assert isinstance(evidence, ClassificationResult)
        model = "lexicon fallback" if evidence.is_fallback else evidence.model_name
        return f"{model} scored this transcript {evidence.percentage}% scam-like."
    if source == "social_engineering":
        assert isinstance(evidence, SocialEngineeringResult)
        count = len(evidence.tactics)
        if not count:
            return "No manipulation tactics were detected."
        names = ", ".join(detection.label for detection in evidence.tactics[:3])
        return f"{count} manipulation tactic(s) detected ({names})."
    assert isinstance(evidence, FactCheckResult)
    if not evidence.verifications:
        return "No checkable factual claims were found."
    return (
        f"{evidence.contradicted_count} claim(s) contradicted and "
        f"{evidence.unverified_count} unverifiable out of {len(evidence.verifications)}."
    )


def compute_risk(
    classification: ClassificationResult,
    social: SocialEngineeringResult,
    fact_check: FactCheckResult,
    *,
    settings: Settings | None = None,
) -> RiskBreakdown:
    """Combine the three agent signals into a 0-100 score with its breakdown."""
    settings = settings or get_settings()
    weights = settings.scoring_weights

    signals: dict[str, tuple[float, object]] = {
        "classifier": (classification.scam_probability, classification),
        "social_engineering": (social.manipulation_score, social),
        "fact_check": (fact_check.risk_contribution, fact_check),
    }

    components: list[EvidenceWeight] = []
    score = 0.0
    for source, (raw, evidence) in signals.items():
        weight = weights[source]
        points = raw * weight * 100.0
        score += points
        components.append(
            EvidenceWeight(
                source=source,
                label=_LABELS[source],
                raw_score=round(raw, 4),
                weight=round(weight, 4),
                weighted_points=round(points, 2),
                rationale=_rationale(source, raw, evidence),
            )
        )

    if fact_check.contradicted_count >= 1 and score < _CRITICAL_FLOOR:
        score = _CRITICAL_FLOOR
        components.append(
            EvidenceWeight(
                source="override",
                label="Decisive contradiction",
                raw_score=1.0,
                weight=0.0,
                weighted_points=0.0,
                rationale=(
                    f"Score raised to {_CRITICAL_FLOOR:.0f}: {fact_check.contradicted_count} "
                    "claim(s) contradict documented policy, which on its own is conclusive."
                ),
            )
        )

    score = round(max(0.0, min(100.0, score)), 1)
    return RiskBreakdown(score=score, level=risk_level_for(score), components=components)


_CATEGORY_HINTS: tuple[tuple[ScamCategory, tuple[str, ...]], ...] = (
    (
        ScamCategory.TECH_SUPPORT,
        ("anydesk", "teamviewer", "microsoft", "windows", "virus", "router", "antivirus"),
    ),
    (
        ScamCategory.GOVERNMENT_IMPERSONATION,
        ("warrant", "nbi", "bureau", "customs", "police", "tax", "social security", "revenue"),
    ),
    (ScamCategory.PRIZE_LOTTERY, ("won", "winner", "raffle", "prize", "promo", "nanalo")),
    (
        ScamCategory.INVESTMENT,
        ("investment", "guaranteed return", "trading", "crypto", "forex", "double your money"),
    ),
    (ScamCategory.DELIVERY_PARCEL, ("parcel", "package", "courier", "delivery", "shipment")),
    (ScamCategory.LOAN_OFFER, ("loan", "pre approved", "pre-approved", "credit line")),
    (
        ScamCategory.FAMILY_EMERGENCY,
        ("accident", "hospital", "your son", "your daughter", "detained", "nabangga"),
    ),
    (
        ScamCategory.JOB_OFFER,
        ("hiring", "job", "employment", "applicant", "salary", "work from home"),
    ),
    (
        ScamCategory.BANK_IMPERSONATION,
        ("bank", "account", "card", "otp", "atm", "fraud department"),
    ),
)


def infer_category(text: str, risk: RiskBreakdown) -> ScamCategory:
    """Best-effort taxonomy label from the transcript's vocabulary."""
    if risk.level in (RiskLevel.SAFE, RiskLevel.LOW):
        return ScamCategory.LEGITIMATE

    lowered = text.lower()
    best: tuple[int, ScamCategory] | None = None
    for category, keywords in _CATEGORY_HINTS:
        hits = sum(1 for keyword in keywords if keyword in lowered)
        if hits and (best is None or hits > best[0]):
            best = (hits, category)
    return best[1] if best else ScamCategory.UNKNOWN
