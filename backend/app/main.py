"""FastAPI application factory and entrypoint.

uvicorn app.main:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, init_db

logger = get_logger(__name__)

DESCRIPTION = """\
ScamShield analyses a recording of a suspicious phone call and returns an
**explainable** scam assessment rather than a bare scam / not-scam label.

Five agents run behind the API:

1. **Speech to text** — Whisper large-v3, with timestamps.
2. **Scam classifier** — TF-IDF + XGBoost, returns a probability and the terms behind it.
3. **Fact verification** — RAG over a knowledge base of bank and agency procedures.
4. **Social engineering analysis** — the psychological tactics used, with quotes.
5. **Report generation** — the user-facing verdict, red flags and next steps.

Each agent degrades to a deterministic analyzer when its optional runtime is not
installed. `GET /api/v1/health/components` reports exactly which path is active.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    settings.ensure_runtime_dirs()
    await init_db()
    logger.info(
        "scamshield_started",
        environment=settings.environment,
        llm=settings.llm_model,
        agents_enabled=settings.agents_enabled,
    )
    yield
    await dispose_engine()
    logger.info("scamshield_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application."""
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="ScamShield API",
        description=DESCRIPTION,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": "ScamShield API",
            "version": "0.1.0",
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health/components",
        }

    return app


app = create_app()
