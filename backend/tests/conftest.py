"""Shared pytest fixtures.

Every test runs against a temporary SQLite file and a temporary upload
directory, and with the LLM disabled so the deterministic path is exercised.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _test_environment(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    root = tmp_path_factory.mktemp("scamshield")
    os.environ.update(
        {
            "SCAMSHIELD_ENVIRONMENT": "test",
            "SCAMSHIELD_DEBUG": "false",
            "SCAMSHIELD_DATABASE_URL": f"sqlite+aiosqlite:///{(root / 'test.db').as_posix()}",
            "SCAMSHIELD_STORAGE_BACKEND": "local",
            "SCAMSHIELD_STORAGE_LOCAL_PATH": str(root / "uploads"),
            "SCAMSHIELD_AGENTS_ENABLED": "false",
            "SCAMSHIELD_TRANSCRIPTION_BACKEND": "stub",
            "SCAMSHIELD_CHROMA_PATH": str(root / "chroma"),
            "SCAMSHIELD_KNOWLEDGE_BASE_PATH": str(BACKEND_ROOT / "data" / "knowledge_base"),
        }
    )

    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[object]:
    """HTTP client bound to the app, with lifespan run."""
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client,
        app.router.lifespan_context(app),
    ):
        yield http_client


SCAM_TRANSCRIPT = (
    "Good afternoon, this is the security department of your bank. "
    "We detected an unauthorized transaction of fifteen thousand pesos on your account. "
    "Your account will be permanently locked within the next 10 minutes. "
    "Please do not hang up and stay on the line. "
    "To reverse the transfer I need you to read me the six digit verification code we just "
    "sent to your phone. "
    "Do not tell anyone about this, it is a confidential security investigation."
)

LEGIT_TRANSCRIPT = (
    "Good afternoon, this is a courtesy call from your bank about your card renewal. "
    "Your replacement card is ready for pickup at your branch. "
    "No action is needed on this call. "
    "If you have questions you can call us back at your convenience using the number at the "
    "back of your card. "
    "We will never ask for your OTP or password. Thank you for being a customer."
)


@pytest.fixture
def scam_transcript() -> str:
    return SCAM_TRANSCRIPT


@pytest.fixture
def legit_transcript() -> str:
    return LEGIT_TRANSCRIPT
