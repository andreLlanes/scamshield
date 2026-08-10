"""Text normalisation shared by training and inference.

Training and serving must clean text identically or the model sees a different
distribution at inference time, so both call :func:`clean_text` here.
"""

from __future__ import annotations

import re
import unicodedata

_URL = re.compile(r"https?://\S+|www\.\S+")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
_MONEY = re.compile(r"(?:php|₱|\$|usd|peso[s]?)\s?\d[\d,.]*", re.IGNORECASE)
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_OTP = re.compile(r"\b\d{4,8}\b")
_WHITESPACE = re.compile(r"\s+")
_PUNCT_RUN = re.compile(r"([!?.,])\1+")

# Numbers and identifiers are replaced with tokens rather than dropped: "send
# ₱15,000" and "your OTP is 493021" are strong signals, but the exact digits
# are noise that would fragment the vocabulary.
_PLACEHOLDERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_URL, " urltoken "),
    (_EMAIL, " emailtoken "),
    (_CARD, " cardnumbertoken "),
    (_MONEY, " moneytoken "),
    (_PHONE, " phonetoken "),
    (_OTP, " codetoken "),
)


def clean_text(text: str) -> str:
    """Lowercase, strip accents, and replace volatile entities with tokens."""
    if not text:
        return ""

    normalised = unicodedata.normalize("NFKD", text)
    normalised = "".join(char for char in normalised if not unicodedata.combining(char))
    normalised = normalised.lower()

    for pattern, replacement in _PLACEHOLDERS:
        normalised = pattern.sub(replacement, normalised)

    normalised = _PUNCT_RUN.sub(r"\1", normalised)
    normalised = re.sub(r"[^a-z0-9\s']", " ", normalised)
    return _WHITESPACE.sub(" ", normalised).strip()


def to_sentences(text: str) -> list[str]:
    """Split raw text into sentences, keeping the original casing."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [part.strip() for part in parts if part.strip()]
