"""Async SQLAlchemy engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import BACKEND_ROOT, Settings, get_settings
from app.core.logging import get_logger
from app.db.base import Base

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _normalised_url(settings: Settings) -> str:
    """Anchor relative SQLite paths to the backend root, not the CWD."""
    url = settings.database_url
    prefix = "sqlite+aiosqlite:///./"
    if url.startswith(prefix):
        target = (BACKEND_ROOT / url[len(prefix) :]).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{target.as_posix()}"
    return url


def get_engine() -> AsyncEngine:
    """Lazily create the process-wide engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            _normalised_url(settings),
            echo=settings.database_echo,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped session."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Session for background work, where there is no request to hang off."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables that do not exist yet.

    Fine for SQLite and for first boot; introduce Alembic before the schema
    starts changing under real data.
    """
    import app.db.models  # noqa: F401  — registers models on Base.metadata

    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    logger.info("database_ready", url=engine.url.render_as_string(hide_password=True))


async def dispose_engine() -> None:
    """Close pooled connections on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
