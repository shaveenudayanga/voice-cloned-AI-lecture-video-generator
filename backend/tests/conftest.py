# SPDX-License-Identifier: Apache-2.0
import os

import pytest
from httpx import ASGITransport, AsyncClient

# Set required env vars before any app import so Settings() does not raise
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")


@pytest.fixture
async def client():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
