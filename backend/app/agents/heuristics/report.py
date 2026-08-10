"""Deterministic report writing (Agent 5's fallback).

Produces the same structure the LLM writer produces, assembled from the
evidence the other agents already gathered. Every red flag carries the quote it
came from, so nothing in the report is unattributable.
"""

from __future__ import annotations

from app.core.constants import ClaimVerdict, RiskLevel, ScamCategory, TacticType
from app.schemas.classification import ClassificationResult
from app.schemas.factcheck import FactCheckResult
from app.schemas.report import RedFlag, RiskBreakdown, ScamReport
from app.schemas.social_engineering import SocialEngineeringResult
from app.schemas.transcript import Transcript

_CATEGORY_TITLES: dict[ScamCategory, str] = {
    ScamCategory.BANK_IMPERSONATION: "bank impersonation scam",
    ScamCategory.GOVERNMENT_IMPERSONATION: "government agency impersonation scam",
    ScamCategory.TECH_SUPPORT: "tech support scam",
    ScamCategory.PRIZE_LOTTERY: "prize or raffle scam",
    ScamCategory.INVESTMENT: "investment scam",
    ScamCategory.DELIVERY_PARCEL: "parcel delivery scam",
    ScamCategory.LOAN_OFFER: "loan offer scam",
    ScamCategory.FAMILY_EMERGENCY: "family emergency scam",
    ScamCategory.JOB_OFFER: "job offer scam",
    ScamCategory.UNKNOWN: "suspicious call",
    ScamCategory.LEGITIMATE: "call",
}

_VERDICT_PREFIX: dict[RiskLevel, str] = {
    RiskLevel.CRITICAL: "Almost certainly a",
    RiskLevel.HIGH: "Likely a",
    RiskLevel.MEDIUM: "Possibly a",
    RiskLevel.LOW: "Probably a legitimate",
    RiskLevel.SAFE: "No scam indicators found in this",
}

_TACTIC_ACTIONS: dict[TacticType, str] = {
    TacticType.AUTHORITY: (
        "Hang up and call the organisation back on the number printed on your card, "
        "statement, or official website — never a number the caller gave you."
    ),
    TacticType.URGENCY: (
        "Ignore the deadline. No genuine bank, agency, or company loses the ability to "
        "help you because you took an hour to verify."
    ),
    TacticType.FEAR: (
        "Do not act on a threat made by phone. Arrests, account closures, and legal "
        "action all come with written notice you can check independently."
    ),
    TacticType.SCARCITY: (
        "Treat 'limited slots' and 'today only' as a warning sign rather than a reason to hurry."
    ),
    TacticType.TRUST: (
        "Knowing your name, address, or partial card number does not prove the caller "
        "works for the institution they name."
    ),
    TacticType.PRESSURE: (
        "End the call. Being told not to hang up is itself the strongest reason to."
    ),
    TacticType.REWARD: (
        "Never pay a fee to release a prize, refund, or loan. Legitimate payouts are "
        "never conditional on you sending money first."
    ),
    TacticType.ISOLATION: (
        "Tell someone. A request for secrecy from family, your bank, or the police is "
        "there to remove the person who would stop you."
    ),
}

_BASE_ACTIONS = [
    "Do not send money, share codes, or install any application requested on this call.",
    "Block the number and report the call to the organisation that was impersonated.",
]

_SAFE_ACTIONS = [
    "Nothing in this recording requires urgent action.",
    "If you are still unsure, call the organisation back on its officially published number.",
]


def _severity_for(score: float) -> RiskLevel:
    if score >= 0.9:
        return RiskLevel.CRITICAL
    if score >= 0.7:
        return RiskLevel.HIGH
    if score >= 0.45:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def build_report(
    transcript: Transcript,
    classification: ClassificationResult,
    social: SocialEngineeringResult,
    fact_check: FactCheckResult,
    risk: RiskBreakdown,
    category: ScamCategory,
) -> ScamReport:
    """Assemble the user-facing report from the collected evidence."""
    red_flags: list[RedFlag] = []

    for verification in fact_check.verifications:
        if verification.verdict != ClaimVerdict.CONTRADICTED:
            continue
        red_flags.append(
            RedFlag(
                title=verification.claim.claim,
                detail=verification.explanation,
                severity=_severity_for(verification.confidence),
                quote=verification.claim.quote or None,
                timestamp=verification.claim.timestamp,
                source_agent="fact_check",
            )
        )

    for detection in social.tactics:
        evidence = detection.evidence[0] if detection.evidence else None
        red_flags.append(
            RedFlag(
                title=f"{detection.label} tactic used",
                detail=(evidence.explanation if evidence else detection.description),
                severity=_severity_for(detection.severity),
                quote=evidence.quote if evidence else None,
                timestamp=evidence.timestamp if evidence else None,
                source_agent="social_engineering",
            )
        )

    if classification.scam_probability >= 0.6 and classification.top_features:
        terms = ", ".join(
            f"“{feature.feature}”"
            for feature in classification.top_features[:4]
            if feature.weight > 0
        )
        if terms:
            red_flags.append(
                RedFlag(
                    title="Language matches known scam scripts",
                    detail=(
                        f"The classifier scored this call {classification.percentage}% scam-like, "
                        f"driven by phrases such as {terms}."
                    ),
                    severity=_severity_for(classification.scam_probability),
                    source_agent="classifier",
                )
            )

    severity_rank = {
        RiskLevel.CRITICAL: 0,
        RiskLevel.HIGH: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.LOW: 3,
        RiskLevel.SAFE: 4,
    }
    red_flags.sort(key=lambda flag: severity_rank[flag.severity])

    # ---- Verdict line -----------------------------------------------------
    prefix = _VERDICT_PREFIX[risk.level]
    noun = _CATEGORY_TITLES.get(category, "suspicious call")
    verdict = (
        f"{prefix} {noun}"
        if risk.level != RiskLevel.SAFE
        else "No scam indicators found in this call"
    )

    # ---- Summary ----------------------------------------------------------
    parts: list[str] = []
    if risk.level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        parts.append(
            f"This call scores {risk.score:.0f}/100 for scam risk, which is a {risk.level.value} "
            "assessment."
        )
    elif risk.level == RiskLevel.MEDIUM:
        parts.append(
            f"This call scores {risk.score:.0f}/100. Some elements are consistent with a scam, "
            "but the evidence is not conclusive."
        )
    else:
        parts.append(
            f"This call scores {risk.score:.0f}/100 for scam risk, which is low. Nothing in the "
            "recording matches a known scam pattern strongly."
        )

    if fact_check.contradicted_count:
        parts.append(
            f"{fact_check.contradicted_count} of the caller's claims contradict how banks, "
            "agencies, or vendors actually operate."
        )
    if social.tactics:
        names = ", ".join(detection.label.lower() for detection in social.tactics[:3])
        parts.append(f"The caller relies on {names} to push for a decision.")
    if fact_check.unverified_count and not fact_check.contradicted_count:
        parts.append(
            f"{fact_check.unverified_count} claim(s) cannot be confirmed from the recording, so "
            "verify them directly with the organisation before acting."
        )

    # ---- Recommended actions ---------------------------------------------
    if risk.level in (RiskLevel.SAFE, RiskLevel.LOW):
        actions = list(_SAFE_ACTIONS)
    else:
        actions = list(_BASE_ACTIONS)
        for detection in social.tactics[:3]:
            action = _TACTIC_ACTIONS.get(detection.tactic)
            if action and action not in actions:
                actions.append(action)
        if fact_check.contradicted_count:
            actions.insert(
                0,
                "Treat this call as a scam: at least one claim the caller made is impossible.",
            )

    return ScamReport(
        verdict=verdict,
        risk=risk,
        category=category,
        summary=" ".join(parts),
        red_flags=red_flags[:10],
        recommended_actions=actions[:6],
        caller_claims=[verification.claim.claim for verification in fact_check.verifications[:6]],
        is_fallback=True,
    )
