# SPDX-License-Identifier: Apache-2.0
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# Set required env vars before any app import so Settings() does not raise
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")


def _make_mock_session() -> AsyncMock:
    """Return a minimal async session mock suitable for auth and route smoke-tests."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar_one.return_value = 0
    session.execute = AsyncMock(return_value=mock_result)
    return session


@pytest.fixture
async def client():
    """App client with a mocked DB session; suitable for auth and basic route tests."""
    from app.db.session import get_session
    from app.main import app

    mock_session = _make_mock_session()

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_session, None)
