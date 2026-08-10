"""Rule-based social engineering detection.

This is Agent 4's fallback, and it is deliberately more than a stub: it runs on
every analysis regardless of whether an LLM is available, which means the
tactic section of the report is never empty and never non-deterministic in the
part that matters most for a user's decision.

Each pattern carries a severity, because "please confirm your name" and "read
me the code or you go to jail" are both Authority but are not equally alarming.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.constants import TacticType
from app.schemas.social_engineering import (
    SocialEngineeringResult,
    TacticDetection,
    TacticEvidence,
)
from app.schemas.transcript import Transcript


@dataclass(frozen=True)
class TacticPattern:
    pattern: re.Pattern[str]
    tactic: TacticType
    severity: float
    explanation: str


def _p(expression: str) -> re.Pattern[str]:
    return re.compile(expression, re.IGNORECASE)


PATTERNS: tuple[TacticPattern, ...] = (
    # ---- Authority --------------------------------------------------------
    TacticPattern(
        _p(
            r"\b(this is|i(?:'m| am) (?:calling )?from|we are (?:calling )?from)\b.{0,40}"
            r"\b(bank|security department|fraud department|police|nbi|bureau|customs|"
            r"revenue|social security|microsoft|windows support|technical support)\b"
        ),
        TacticType.AUTHORITY,
        0.8,
        "The caller borrows the credibility of an institution to justify unusual requests.",
    ),
    TacticPattern(
        _p(r"\b(officer|agent|investigator|representative|badge number|case number)\b"),
        TacticType.AUTHORITY,
        0.5,
        "The caller adopts an official-sounding role or reference to appear authorised.",
    ),
    # ---- Urgency ----------------------------------------------------------
    TacticPattern(
        _p(
            r"\b(within the next|in the next|you (?:only )?have)\s+\w+\s*"
            r"(minutes?|hours?|seconds?)\b"
        ),
        TacticType.URGENCY,
        0.85,
        "A countdown is imposed so there is no time to verify the caller.",
    ),
    TacticPattern(
        _p(
            r"\b(right now|immediately|as soon as possible|expires today|before (?:the )?"
            r"(?:day|office|market) (?:ends|closes)|bilisan mo|ngayon din|last chance)\b"
        ),
        TacticType.URGENCY,
        0.6,
        "The caller compresses the decision window to prevent independent checking.",
    ),
    # ---- Fear -------------------------------------------------------------
    TacticPattern(
        _p(
            r"\b(warrant of arrest|be arrested|legal action|lawsuit|criminal case|"
            r"money laundering|charges will be filed|blotter)\b"
        ),
        TacticType.FEAR,
        0.95,
        "Threat of arrest or prosecution is used to override the target's judgement.",
    ),
    TacticPattern(
        _p(
            r"\b(permanently (?:locked|closed|blocked)|account will be (?:closed|frozen|suspended|"
            r"deactivated)|lose (?:your|all your) (?:money|savings|funds)|"
            r"unauthorized transaction|has been compromised|hacked)\b"
        ),
        TacticType.FEAR,
        0.8,
        "A loss or lock-out is threatened to trigger a panicked response.",
    ),
    # ---- Scarcity ---------------------------------------------------------
    TacticPattern(
        _p(
            r"\b(limited (?:slots?|offer|time)|only \w+ (?:slots?|left)|one[- ]time (?:offer|only)|"
            r"exclusive|first come|while supplies last|today only)\b"
        ),
        TacticType.SCARCITY,
        0.65,
        "The offer is framed as scarce so hesitation feels like a loss.",
    ),
    # ---- Trust ------------------------------------------------------------
    TacticPattern(
        _p(
            r"\b(reference number|verification number|ticket number|badge|employee id|"
            r"i can see your|our records show|as you can see on your)\b"
        ),
        TacticType.TRUST,
        0.55,
        "Fabricated identifiers and 'records' are cited to manufacture legitimacy.",
    ),
    TacticPattern(
        _p(
            r"\b(for your (?:protection|security|safety)|to protect your (?:account|money|funds)|"
            r"we are here to help you)\b"
        ),
        TacticType.TRUST,
        0.6,
        "The request is reframed as protective so compliance feels like self-defence.",
    ),
    # ---- Pressure ---------------------------------------------------------
    TacticPattern(
        _p(
            r"\b(do not hang up|don'?t hang up|stay on the line|remain on the line|"
            r"keep the line open|huwag mong ibaba)\b"
        ),
        TacticType.PRESSURE,
        0.95,
        "Keeping the target on the line prevents any independent verification call.",
    ),
    TacticPattern(
        _p(
            r"\b(you (?:must|need to|have to) (?:do this|comply|cooperate)|"
            r"there is no other (?:way|option)|i cannot (?:wait|hold)|"
            r"if you (?:refuse|don'?t))\b"
        ),
        TacticType.PRESSURE,
        0.7,
        "The caller removes the option of declining or deferring.",
    ),
    # ---- Reward -----------------------------------------------------------
    TacticPattern(
        _p(
            r"\b(you (?:have )?won|congratulations|lucky winner|cash prize|raffle|"
            r"guaranteed return|double your money|no risk|pre[- ]approved|tax refund|"
            r"rebate|nanalo ka)\b"
        ),
        TacticType.REWARD,
        0.8,
        "A prize, refund, or guaranteed gain is dangled to motivate a payment or disclosure.",
    ),
    # ---- Isolation --------------------------------------------------------
    TacticPattern(
        _p(
            r"\b(do not tell|don'?t tell|keep this (?:confidential|between us|a secret)|"
            r"do not (?:discuss|mention) this|without telling|huwag mong sabihin|"
            r"do not inform (?:the bank|your family|anyone))\b"
        ),
        TacticType.ISOLATION,
        1.0,
        "Secrecy is demanded so nobody can talk the target out of it.",
    ),
    # ---- Credential extraction (reported as Authority + Pressure) ----------
    TacticPattern(
        _p(
            r"\b(read me the|give me the|what(?:'s| is) the)\b.{0,25}"
            r"\b(code|otp|pin|password|cvv)\b"
        ),
        TacticType.PRESSURE,
        1.0,
        "A direct demand for a secret code — no legitimate caller ever makes this request.",
    ),
)


def _dedupe(evidence: list[TacticEvidence]) -> list[TacticEvidence]:
    seen: set[str] = set()
    unique: list[TacticEvidence] = []
    for item in evidence:
        key = item.quote.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def analyze(transcript: Transcript) -> SocialEngineeringResult:
    """Detect manipulation tactics and cite the line each one came from."""
    segments = transcript.segments or []
    haystack: list[tuple[str, str | None]] = (
        [(segment.text, segment.timestamp) for segment in segments]
        if segments
        else [(transcript.text, None)]
    )

    found: dict[TacticType, list[tuple[float, TacticEvidence]]] = {}
    for text, timestamp in haystack:
        for rule in PATTERNS:
            if rule.pattern.search(text):
                found.setdefault(rule.tactic, []).append(
                    (
                        rule.severity,
                        TacticEvidence(
                            quote=text.strip(),
                            timestamp=timestamp,
                            explanation=rule.explanation,
                        ),
                    )
                )

    detections: list[TacticDetection] = []
    for tactic, matches in found.items():
        severities = [severity for severity, _ in matches]
        evidence = _dedupe([item for _, item in matches])
        # Repeated hits raise confidence but the strongest match sets severity.
        confidence = min(0.55 + 0.15 * (len(evidence) - 1), 0.95)
        detections.append(
            TacticDetection(
                tactic=tactic,
                confidence=round(confidence, 2),
                severity=round(max(severities), 2),
                evidence=evidence[:3],
            )
        )

    detections.sort(key=lambda d: d.confidence * d.severity, reverse=True)
    score = SocialEngineeringResult.score_from(detections)

    if detections:
        names = ", ".join(detection.label for detection in detections[:4])
        summary = (
            f"Detected {len(detections)} manipulation "
            f"{'tactic' if len(detections) == 1 else 'tactics'} in this call: {names}."
        )
    else:
        summary = "No recognised social engineering tactics were found in this recording."

    return SocialEngineeringResult(
        tactics=detections,
        summary=summary,
        manipulation_score=score,
        is_fallback=True,
    )
