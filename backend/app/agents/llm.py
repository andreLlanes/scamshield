"""LLM wiring for the CrewAI agents.

The model string carries the provider (``ollama/llama3.1:8b``,
``anthropic/claude-sonnet-5``, ``openai/gpt-4o-mini``), which is how both
CrewAI and LiteLLM route calls. Nothing else in the codebase needs to know
which provider is in use.
"""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMUnavailable(RuntimeError):
    """Raised when no usable LLM is configured; callers fall back to heuristics."""


@lru_cache(maxsize=1)
def crewai_installed() -> bool:
    return importlib.util.find_spec("crewai") is not None


def _ollama_reachable(base_url: str, timeout: float = 2.0) -> bool:
    """Cheap liveness probe so a stopped Ollama degrades instead of hanging."""
    import httpx  # noqa: PLC0415

    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def llm_status(settings: Settings | None = None) -> tuple[bool, str]:
    """Return ``(ready, reason)`` for the configured LLM."""
    settings = settings or get_settings()

    if not settings.agents_enabled:
        return False, "Agents disabled via SCAMSHIELD_AGENTS_ENABLED=false"
    if not crewai_installed():
        return False, "crewai is not installed (pip install -e '.[agents]')"

    model = settings.llm_model
    if model.startswith("ollama/"):
        base_url = settings.llm_base_url or "http://localhost:11434"
        if not _ollama_reachable(base_url):
            return False, f"Ollama is not reachable at {base_url}"
        return True, f"Ollama · {model.split('/', 1)[1]}"

    import os  # noqa: PLC0415

    required_key = {
        "anthropic/": "ANTHROPIC_API_KEY",
        "openai/": "OPENAI_API_KEY",
        "gemini/": "GEMINI_API_KEY",
        "groq/": "GROQ_API_KEY",
    }
    for prefix, env_var in required_key.items():
        if model.startswith(prefix) and not os.environ.get(env_var):
            return False, f"{env_var} is not set for model {model}"

    return True, model


def build_llm(settings: Settings | None = None) -> Any:
    """Construct the CrewAI LLM object, or raise :class:`LLMUnavailable`."""
    settings = settings or get_settings()
    ready, reason = llm_status(settings)
    if not ready:
        raise LLMUnavailable(reason)

    from crewai import LLM  # noqa: PLC0415  — optional extra

    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "timeout": settings.llm_timeout_seconds,
    }
    if settings.llm_base_url and settings.llm_model.startswith("ollama/"):
        kwargs["base_url"] = settings.llm_base_url

    logger.info("llm_configured", model=settings.llm_model)
    return LLM(**kwargs)


@lru_cache(maxsize=1)
def get_llm() -> Any:
    """Cached LLM handle (CrewAI LLM objects are safe to reuse)."""
    return build_llm()


def reset_llm_cache() -> None:
    """Drop cached LLM state — used by tests and after a config change."""
    get_llm.cache_clear()
    crewai_installed.cache_clear()
