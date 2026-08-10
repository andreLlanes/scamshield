"""Weighted scam lexicon.

Two jobs:

1. It backs the fallback scorer, so the classifier still returns a calibrated
   number on a machine where no trained artifact exists yet.
2. It supplies human-readable phrases for the report when the trained model's
   n-grams are too fragmentary to show a user.

Phrases cover English and the Taglish register common in Philippine phone
scams, which is the deployment context named in the project brief.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ml.classifier.preprocessing import clean_text


@dataclass(frozen=True)
class LexiconEntry:
    """A phrase that moves the scam score, and by how much."""

    phrase: str
    weight: float
    category: str


# Positive weights push toward "scam"; negative weights pull toward "legitimate".
SCAM_LEXICON: tuple[LexiconEntry, ...] = (
    # --- Credential / OTP harvesting: the single strongest signal -----------
    LexiconEntry("otp", 1.0, "credential"),
    LexiconEntry("one time password", 1.0, "credential"),
    LexiconEntry("verification code", 0.95, "credential"),
    LexiconEntry("code sent to your phone", 1.0, "credential"),
    LexiconEntry("read me the code", 1.1, "credential"),
    LexiconEntry("give me the code", 1.1, "credential"),
    LexiconEntry("your pin", 1.0, "credential"),
    LexiconEntry("card number", 0.9, "credential"),
    LexiconEntry("cvv", 1.0, "credential"),
    LexiconEntry("expiry date", 0.6, "credential"),
    LexiconEntry("mother's maiden name", 0.8, "credential"),
    LexiconEntry("online banking password", 1.1, "credential"),
    LexiconEntry("confirm your account number", 0.75, "credential"),
    LexiconEntry("ibigay mo ang code", 1.1, "credential"),
    # --- Payment coercion ---------------------------------------------------
    LexiconEntry("gcash", 0.5, "payment"),
    LexiconEntry("send money", 0.7, "payment"),
    LexiconEntry("wire transfer", 0.65, "payment"),
    LexiconEntry("gift card", 0.95, "payment"),
    LexiconEntry("google play card", 1.0, "payment"),
    LexiconEntry("steam card", 1.0, "payment"),
    LexiconEntry("bitcoin", 0.85, "payment"),
    LexiconEntry("crypto wallet", 0.85, "payment"),
    LexiconEntry("processing fee", 0.8, "payment"),
    LexiconEntry("release fee", 0.85, "payment"),
    LexiconEntry("clearance fee", 0.85, "payment"),
    LexiconEntry("advance payment", 0.7, "payment"),
    LexiconEntry("remittance center", 0.6, "payment"),
    LexiconEntry("padalhan mo ako", 0.7, "payment"),
    LexiconEntry("transfer the funds", 0.7, "payment"),
    LexiconEntry("safe account", 1.0, "payment"),
    LexiconEntry("holding account", 0.9, "payment"),
    # --- Authority impersonation -------------------------------------------
    LexiconEntry("bank security department", 0.8, "authority"),
    LexiconEntry("fraud department", 0.6, "authority"),
    LexiconEntry("anti money laundering", 0.7, "authority"),
    LexiconEntry("bureau of internal revenue", 0.6, "authority"),
    LexiconEntry("national bureau of investigation", 0.7, "authority"),
    LexiconEntry("nbi", 0.6, "authority"),
    LexiconEntry("social security", 0.5, "authority"),
    LexiconEntry("customs", 0.55, "authority"),
    LexiconEntry("warrant of arrest", 1.0, "authority"),
    LexiconEntry("legal action", 0.7, "authority"),
    LexiconEntry("microsoft technical support", 0.9, "authority"),
    LexiconEntry("windows support", 0.85, "authority"),
    # --- Urgency and fear ---------------------------------------------------
    LexiconEntry("within the next", 0.4, "urgency"),
    LexiconEntry("in the next 10 minutes", 0.85, "urgency"),
    LexiconEntry("right now", 0.35, "urgency"),
    LexiconEntry("immediately", 0.4, "urgency"),
    LexiconEntry("permanently locked", 0.9, "urgency"),
    LexiconEntry("account will be closed", 0.85, "urgency"),
    LexiconEntry("account has been compromised", 0.8, "urgency"),
    LexiconEntry("suspicious transaction", 0.6, "urgency"),
    LexiconEntry("unauthorized transaction", 0.6, "urgency"),
    LexiconEntry("frozen", 0.6, "urgency"),
    LexiconEntry("deactivated", 0.6, "urgency"),
    LexiconEntry("last chance", 0.75, "urgency"),
    LexiconEntry("expires today", 0.7, "urgency"),
    LexiconEntry("bilisan mo", 0.6, "urgency"),
    # --- Reward bait --------------------------------------------------------
    LexiconEntry("you have won", 0.95, "reward"),
    LexiconEntry("congratulations you", 0.7, "reward"),
    LexiconEntry("lucky winner", 1.0, "reward"),
    LexiconEntry("cash prize", 0.9, "reward"),
    LexiconEntry("raffle", 0.7, "reward"),
    LexiconEntry("tax refund", 0.75, "reward"),
    LexiconEntry("guaranteed return", 0.95, "reward"),
    LexiconEntry("double your money", 1.1, "reward"),
    LexiconEntry("investment opportunity", 0.7, "reward"),
    LexiconEntry("no risk", 0.7, "reward"),
    LexiconEntry("pre approved loan", 0.75, "reward"),
    LexiconEntry("nanalo ka", 1.0, "reward"),
    # --- Isolation / secrecy ------------------------------------------------
    LexiconEntry("do not tell anyone", 1.1, "isolation"),
    LexiconEntry("don't tell your family", 1.1, "isolation"),
    LexiconEntry("keep this confidential", 0.9, "isolation"),
    LexiconEntry("stay on the line", 0.85, "isolation"),
    LexiconEntry("do not hang up", 1.0, "isolation"),
    LexiconEntry("huwag mong sabihin", 1.0, "isolation"),
    # --- Remote access ------------------------------------------------------
    LexiconEntry("anydesk", 1.0, "remote_access"),
    LexiconEntry("teamviewer", 1.0, "remote_access"),
    LexiconEntry("remote access", 0.9, "remote_access"),
    LexiconEntry("install this app", 0.8, "remote_access"),
    LexiconEntry("click the link i sent", 0.85, "remote_access"),
    # --- Legitimate-call markers (negative weight) --------------------------
    LexiconEntry("we will never ask", -1.0, "legitimate"),
    LexiconEntry("never ask for your otp", -1.2, "legitimate"),
    LexiconEntry("please visit our branch", -0.8, "legitimate"),
    LexiconEntry("you can call the number at the back of your card", -1.0, "legitimate"),
    LexiconEntry("reference number for your records", -0.5, "legitimate"),
    LexiconEntry("no action is needed", -0.7, "legitimate"),
    LexiconEntry("take your time", -0.6, "legitimate"),
    LexiconEntry("call us back at your convenience", -0.9, "legitimate"),
    LexiconEntry("this call is recorded for quality", -0.4, "legitimate"),
    LexiconEntry("your appointment", -0.6, "legitimate"),
    LexiconEntry("your delivery is scheduled", -0.5, "legitimate"),
    LexiconEntry("thank you for being a customer", -0.4, "legitimate"),
)

_COMPILED: tuple[tuple[re.Pattern[str], LexiconEntry], ...] = tuple(
    (re.compile(rf"\b{re.escape(clean_text(entry.phrase))}\b"), entry)
    for entry in SCAM_LEXICON
    if clean_text(entry.phrase)
)


@dataclass(frozen=True)
class LexiconHit:
    entry: LexiconEntry
    occurrences: int


def match(text: str) -> list[LexiconHit]:
    """Return every lexicon entry present in ``text``, with hit counts."""
    cleaned = clean_text(text)
    hits: list[LexiconHit] = []
    for pattern, entry in _COMPILED:
        found = len(pattern.findall(cleaned))
        if found:
            hits.append(LexiconHit(entry=entry, occurrences=found))
    return hits


def score(text: str) -> tuple[float, list[LexiconHit]]:
    """Score ``text`` in 0-1 using a saturating sum of lexicon weights.

    Repeated phrases add with diminishing returns (``sqrt`` of the count), and
    the total is squashed with a logistic so that a call has to stack several
    independent signals before it reaches a high score.
    """
    import math

    hits = match(text)
    if not hits:
        return 0.0, []

    total = sum(hit.entry.weight * math.sqrt(hit.occurrences) for hit in hits)
    probability = 1.0 / (1.0 + math.exp(-(total - 1.6) / 1.2))
    ranked = sorted(hits, key=lambda hit: abs(hit.entry.weight), reverse=True)
    return round(probability, 4), ranked
