"""Rule-based claim extraction and verification (Agent 3's fallback).

Extraction finds the checkable assertions in a call. Verification then decides
each one against the knowledge base:

* ``contradicted`` — the claim asserts something that established policy says
  cannot happen ("give me the OTP", "transfer to a safe account").
* ``verified``     — the claim matches documented legitimate practice.
* ``unverified``   — plausible but uncheckable from a recording alone, which is
  the correct answer for most identity claims by an unknown caller.

Every verdict is returned with the knowledge-base passage that justified it, so
the report can show the user *why*, not just *what*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.constants import ClaimVerdict
from app.ml.rag.retriever import KnowledgeRetriever
from app.schemas.factcheck import ClaimVerification, FactCheckResult, FactualClaim
from app.schemas.transcript import Transcript


def _p(expression: str) -> re.Pattern[str]:
    return re.compile(expression, re.IGNORECASE)


# A legitimate call often *mentions* OTPs, fees, or remote access in order to
# warn against them ("we will never ask for your OTP"). Matching the keyword
# alone would turn that advice into a contradiction, so rules that key off such
# keywords are suppressed when the same sentence is phrased as a warning.
_ADVISORY = _p(
    r"\b(?:never|will not|won'?t|do not|don'?t|no need to|cannot|can'?t)\b[^.?!]{0,40}?"
    r"\b(?:ask|share|request|require|give|provide|send|disclose|need)\b"
)


@dataclass(frozen=True)
class ClaimRule:
    pattern: re.Pattern[str]
    category: str
    claim_template: str
    query: str
    verdict: ClaimVerdict
    confidence: float
    explanation: str
    # True when this rule keys off a keyword an honest caller might use in a
    # warning; such rules are skipped on advisory sentences.
    advisory_sensitive: bool = False


RULES: tuple[ClaimRule, ...] = (
    # ---- Contradicted by documented policy --------------------------------
    ClaimRule(
        _p(
            r"\b(otp|one[- ]time password|verification code|code (?:we|i) (?:just )?sent|"
            r"code sent to your phone|read me the code|give me the code|ibigay mo ang code)\b"
        ),
        "credential",
        "The caller needs a one-time password or verification code from the recipient.",
        "Do banks ever ask customers for their OTP or verification code?",
        ClaimVerdict.CONTRADICTED,
        0.97,
        "No bank, wallet provider, or agency ever asks for a one-time password. The OTP "
        "exists to authorise a transaction the caller is trying to make.",
        advisory_sensitive=True,
    ),
    ClaimRule(
        _p(
            r"\b(your pin|online banking password|\bcvv\b|card number|mother'?s maiden name|"
            r"expiry date)\b"
        ),
        "credential",
        "The caller asks for card or banking credentials to verify identity.",
        "Do banks ask for PIN, CVV, or online banking passwords over the phone?",
        ClaimVerdict.CONTRADICTED,
        0.95,
        "Institutions authenticate customers through their own systems and never need a "
        "PIN, CVV, or banking password recited over the phone.",
        advisory_sensitive=True,
    ),
    ClaimRule(
        _p(
            r"\b(safe account|holding account|secure account|temporary account|"
            r"transfer (?:your|the) (?:funds|balance|money) (?:to|for))\b"
        ),
        "procedure",
        "The caller says funds must be moved to a safe or holding account.",
        "Do banks ask customers to move money to a safe account?",
        ClaimVerdict.CONTRADICTED,
        0.96,
        "No 'safe account' procedure exists. A bank that suspects compromise blocks the "
        "account itself rather than asking the customer to move money.",
        advisory_sensitive=True,
    ),
    ClaimRule(
        _p(
            r"\b(warrant of arrest|you will be arrested|arrest warrant|criminal case against you)\b"
        ),
        "legal",
        "The caller claims a warrant or criminal case exists against the recipient.",
        "Are arrest warrants settled over the phone by paying a fee?",
        ClaimVerdict.CONTRADICTED,
        0.93,
        "Warrants are issued by courts and served in person. No agency cancels one over "
        "the phone in exchange for a payment.",
    ),
    ClaimRule(
        _p(r"\b(gift card|google play (?:card|code)|steam card|itunes card|prepaid load)\b"),
        "payment",
        "The caller asks for payment in gift card or prepaid codes.",
        "Is payment by gift card ever legitimate for fees or fines?",
        ClaimVerdict.CONTRADICTED,
        0.98,
        "No legitimate organisation accepts gift-card codes as payment. Once read aloud "
        "the value is gone and untraceable.",
        advisory_sensitive=True,
    ),
    ClaimRule(
        _p(
            r"\b(processing fee|release fee|clearance fee|registration fee|insurance fee|"
            r"advance payment|activation fee)\b"
        ),
        "payment",
        "The caller requires a fee to be paid before money, a prize, or goods are released.",
        "Do legitimate prizes, loans, or refunds require an advance fee?",
        ClaimVerdict.CONTRADICTED,
        0.9,
        "Genuine prizes, loan releases, and refunds are never conditioned on the recipient "
        "paying a fee first; deductions are netted from the amount.",
        advisory_sensitive=True,
    ),
    ClaimRule(
        _p(
            r"\b(guaranteed return|no risk|double your money|risk[- ]free|"
            r"guaranteed (?:profit|income))\b"
        ),
        "offer",
        "The caller promises a guaranteed or risk-free financial return.",
        "Can an investment guarantee returns with no risk?",
        ClaimVerdict.CONTRADICTED,
        0.94,
        "No investment can guarantee a high return with no risk. Guaranteed-return pitches "
        "describe a Ponzi structure, not a regulated product.",
    ),
    ClaimRule(
        _p(
            r"\b(anydesk|teamviewer|quicksupport|remote access|install (?:this|the) app|"
            r"share your screen)\b"
        ),
        "procedure",
        "The caller wants remote access to the recipient's device.",
        "Do banks or software vendors need remote access to a customer's device?",
        ClaimVerdict.CONTRADICTED,
        0.95,
        "Remote-access tools hand the caller control of the device and its banking apps. "
        "No genuine support process requires them.",
        advisory_sensitive=True,
    ),
    ClaimRule(
        _p(
            r"\b(social security (?:number )?(?:has been )?suspended|tin (?:has been )?suspended|"
            r"your (?:id|number) (?:has been|is) (?:suspended|blocked|deactivated))\b"
        ),
        "identity",
        "The caller claims a government identification number has been suspended.",
        "Can a social security number or TIN be suspended for suspicious activity?",
        ClaimVerdict.CONTRADICTED,
        0.92,
        "Identification numbers are not suspended for 'suspicious activity'. The claim "
        "appears only in impersonation scripts.",
    ),
    ClaimRule(
        _p(
            r"\b(unsolicited|we detected a virus|your computer is (?:infected|sending)|"
            r"windows (?:licence|license) (?:has )?expired|your router (?:has been )?infected)\b"
        ),
        "identity",
        "The caller claims to have detected a problem on the recipient's computer.",
        "Can Microsoft or an antivirus vendor detect a virus and phone the user?",
        ClaimVerdict.CONTRADICTED,
        0.93,
        "Software vendors cannot detect an infection on a specific consumer machine, and "
        "they do not make unsolicited support calls.",
    ),
    # ---- Consistent with documented legitimate practice --------------------
    ClaimRule(
        _p(
            r"\b(we will never ask|never ask for your (?:otp|pin|password)|"
            r"do not share (?:any|your) (?:code|otp)|please do not share)\b"
        ),
        "procedure",
        "The caller states that the organisation will never ask for codes or passwords.",
        "What do banks say about never asking for OTPs?",
        ClaimVerdict.VERIFIED,
        0.85,
        "This matches documented bank policy — genuine notifications include exactly this warning.",
    ),
    ClaimRule(
        _p(
            r"\b(call (?:us )?back at your convenience|number at the back of your card|"
            r"visit (?:our|any) branch|no action is needed|take your time|"
            r"call the official hotline)\b"
        ),
        "procedure",
        "The caller invites the recipient to verify independently or take no action.",
        "Do legitimate callers allow you to hang up and call back to verify?",
        ClaimVerdict.VERIFIED,
        0.8,
        "Inviting independent verification is consistent with legitimate practice; scam "
        "callers resist it.",
    ),
    # ---- Checkable but not confirmable from a recording --------------------
    ClaimRule(
        _p(
            r"\b(?:this is|i(?:'m| am)(?: calling)? from|we are (?:calling )?from)\b"
            r".{0,40}\b(bank|department|bureau|agency|office|police|support|company)\b"
        ),
        "identity",
        "The caller states which organisation they represent.",
        "Can caller ID or a spoken claim prove which organisation a caller works for?",
        ClaimVerdict.UNVERIFIED,
        0.75,
        "A spoken affiliation cannot be confirmed from a recording, and caller ID is "
        "trivially spoofed. Verify by calling the organisation's published number.",
    ),
    ClaimRule(
        _p(r"\b(suspicious|unauthorized|unauthorised) (?:transaction|activity|login|access)\b"),
        "procedure",
        "The caller claims suspicious activity was detected on the recipient's account.",
        "How do banks notify customers about suspicious transactions?",
        ClaimVerdict.UNVERIFIED,
        0.7,
        "Whether a flagged transaction really exists can only be confirmed through the "
        "bank's app or its published hotline, not by the caller.",
    ),
    ClaimRule(
        _p(r"\b(you (?:have )?won|lucky winner|cash prize|raffle|you have been selected)\b"),
        "offer",
        "The caller claims the recipient has won a prize or promotion.",
        "How can a raffle or promo win be verified?",
        ClaimVerdict.UNVERIFIED,
        0.75,
        "A win in a promotion the recipient never entered cannot be substantiated; genuine "
        "promos publish winners through official channels.",
    ),
    ClaimRule(
        _p(
            r"\b(your (?:parcel|package|delivery|shipment))\b.{0,60}"
            r"\b(held|hold|customs|pending|stuck|failed)\b"
        ),
        "procedure",
        "The caller claims a parcel is being held pending payment.",
        "How are customs duties on a held parcel actually collected?",
        ClaimVerdict.UNVERIFIED,
        0.7,
        "Genuine duties come with a written assessment and a tracking reference payable "
        "through official channels — check with the courier directly.",
    ),
)


async def extract_and_verify(
    transcript: Transcript, retriever: KnowledgeRetriever
) -> FactCheckResult:
    """Extract checkable claims and judge each against the knowledge base."""
    segments = transcript.segments or []
    haystack: list[tuple[str, str | None]] = (
        [(segment.text, segment.timestamp) for segment in segments]
        if segments
        else [(transcript.text, None)]
    )

    # Keep the earliest, most quotable occurrence of each distinct claim.
    matched: dict[str, tuple[ClaimRule, str, str | None]] = {}
    for text, timestamp in haystack:
        is_advisory = _ADVISORY.search(text) is not None
        for rule in RULES:
            if rule.claim_template in matched:
                continue
            if rule.advisory_sensitive and is_advisory:
                continue
            if rule.pattern.search(text):
                matched[rule.claim_template] = (rule, text.strip(), timestamp)

    if not matched:
        return FactCheckResult(
            verifications=[],
            summary="No specific factual claims could be extracted from this recording.",
            is_fallback=True,
        )

    evidence_map = await retriever.search_many(
        [rule.query for rule, _, _ in matched.values()], top_k=2
    )

    verifications: list[ClaimVerification] = []
    for rule, quote, timestamp in matched.values():
        verifications.append(
            ClaimVerification(
                claim=FactualClaim(
                    claim=rule.claim_template,
                    quote=quote,
                    timestamp=timestamp,
                    category=rule.category,
                ),
                verdict=rule.verdict,
                confidence=rule.confidence,
                explanation=rule.explanation,
                evidence=evidence_map.get(rule.query, []),
            )
        )

    # Most alarming first: contradicted, then unverified, then verified.
    order = {ClaimVerdict.CONTRADICTED: 0, ClaimVerdict.UNVERIFIED: 1, ClaimVerdict.VERIFIED: 2}
    verifications.sort(key=lambda item: (order[item.verdict], -item.confidence))

    result = FactCheckResult(verifications=verifications, is_fallback=True)
    contradicted = result.contradicted_count
    if contradicted:
        result.summary = (
            f"{contradicted} of the caller's {len(verifications)} checkable claims directly "
            "contradict documented bank, agency, or vendor policy."
        )
    elif result.unverified_count:
        result.summary = (
            f"None of the {len(verifications)} extracted claims contradict known policy, but "
            f"{result.unverified_count} cannot be confirmed from the recording alone."
        )
    else:
        result.summary = "The caller's claims are consistent with documented legitimate practice."
    return result
