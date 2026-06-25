# SPDX-License-Identifier: Apache-2.0
import pytest


@pytest.mark.asyncio
async def test_liveness_returns_ok(client) -> None:
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
