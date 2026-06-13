from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Create the async engine lazily (safe for subprocess/spawn workers)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database.url_async,
            echo=settings.app.debug,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autobegin=False,
        )
    return _async_session_factory


class _LazyEngine:
    """Backward-compatible proxy for `from app.core.database import engine`."""

    def __getattr__(self, name: str):
        return getattr(get_engine(), name)

    async def dispose(self) -> None:
        global _engine, _async_session_factory
        if _engine is not None:
            await _engine.dispose()
            _engine = None
            _async_session_factory = None


engine = _LazyEngine()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting database session."""
    async with get_async_session_factory()() as session:
        yield session


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for getting database session (for daemons/scripts)."""
    async with get_async_session_factory()() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_session)]
