"""Tolerant parsing of LLM output.

Small local models wrap JSON in prose, fences, or a preamble. Rather than
failing the whole analysis on formatting, these helpers recover the payload and
let the caller fall back only when nothing usable is present.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _balanced_slice(text: str, opener: str, closer: str) -> str | None:
    """Extract the first balanced ``opener…closer`` region, ignoring braces in strings."""
    start = text.find(opener)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def extract_json(text: str) -> Any | None:
    """Best-effort recovery of a JSON object or array from ``text``."""
    if not text:
        return None

    candidates: list[str] = []
    stripped = text.strip()
    candidates.append(stripped)
    candidates.extend(match.strip() for match in _FENCE.findall(text))
    for opener, closer in (("{", "}"), ("[", "]")):
        found = _balanced_slice(text, opener, closer)
        if found:
            candidates.append(found)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue

    # Last resort: models sometimes emit trailing commas or single quotes.
    for candidate in candidates:
        repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(repaired)
        except (json.JSONDecodeError, TypeError):
            continue

    logger.debug("json_extraction_failed", preview=text[:200])
    return None


def parse_model(text: str, model: type[T]) -> T | None:
    """Parse ``text`` into ``model``, returning ``None`` when it cannot be salvaged."""
    payload = extract_json(text)
    if payload is None:
        return None
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        logger.debug("model_validation_failed", model=model.__name__, errors=exc.error_count())
        return None


def parse_list(text: str, key: str | None = None) -> list[dict[str, Any]]:
    """Parse a list of objects, unwrapping ``{"<key>": [...]}`` when needed."""
    payload = extract_json(text)
    if payload is None:
        return []
    if isinstance(payload, dict):
        if key and isinstance(payload.get(key), list):
            payload = payload[key]
        else:
            for value in payload.values():
                if isinstance(value, list):
                    payload = value
                    break
            else:
                payload = [payload]
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def coerce_float(value: Any, default: float = 0.5, *, low: float = 0.0, high: float = 1.0) -> float:
    """Read a number that may arrive as ``0.8``, ``"0.8"``, ``"80%"`` or ``80``."""
    if isinstance(value, bool):
        return default
    try:
        if isinstance(value, str):
            cleaned = value.strip().rstrip("%")
            number = float(cleaned)
            if value.strip().endswith("%") or number > 1.0:
                number /= 100.0
        else:
            number = float(value)
            if number > 1.0:
                number /= 100.0
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))
