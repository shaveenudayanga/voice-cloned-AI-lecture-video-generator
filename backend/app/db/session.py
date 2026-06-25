# SPDX-License-Identifier: Apache-2.0
from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = structlog.get_logger(__name__)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_engine() -> None:
    global _engine, _session_factory
    _engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=settings.debug,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    logger.info("db_engine_initialized")


async def close_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        logger.info("db_engine_closed")


async def get_session() -> AsyncGenerator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB engine not initialized")
    async with _session_factory() as session:
        yield session


async def get_task_session() -> AsyncSession:
    """Create a one-shot async session for use inside Celery task coroutines.

    Unlike get_session(), this is not a generator — the caller is responsible
    for committing and closing the session.
    """
    db_url = settings.database_url
    engine = create_async_engine(db_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()
    return session
