# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_liveness_returns_ok(client) -> None:
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_all_ok(client) -> None:
    """All three checks pass → status ok."""
    with (
        patch("app.api.v1.health._ping_valkey", new=AsyncMock(return_value="ok")),
        patch("app.api.v1.health._ping_seaweedfs", new=AsyncMock(return_value="ok")),
    ):
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["postgres"] == "ok"
    assert data["checks"]["valkey"] == "ok"
    assert data["checks"]["seaweedfs"] == "ok"


@pytest.mark.asyncio
async def test_readiness_valkey_down(client) -> None:
    """Valkey unreachable → 200 with degraded status, error in checks."""
    with (
        patch(
            "app.api.v1.health._ping_valkey",
            new=AsyncMock(return_value="error: Connection refused"),
        ),
        patch("app.api.v1.health._ping_seaweedfs", new=AsyncMock(return_value="ok")),
    ):
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["valkey"].startswith("error:")
    assert data["checks"]["seaweedfs"] == "ok"


@pytest.mark.asyncio
async def test_readiness_seaweedfs_down(client) -> None:
    """SeaweedFS unreachable → 200 with degraded status, error in checks."""
    with (
        patch("app.api.v1.health._ping_valkey", new=AsyncMock(return_value="ok")),
        patch(
            "app.api.v1.health._ping_seaweedfs",
            new=AsyncMock(return_value="error: ConnectError"),
        ),
    ):
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["valkey"] == "ok"
    assert data["checks"]["seaweedfs"].startswith("error:")


@pytest.mark.asyncio
async def test_readiness_multiple_deps_down(client) -> None:
    """Both Valkey and SeaweedFS down → degraded, both checks show error."""
    with (
        patch(
            "app.api.v1.health._ping_valkey",
            new=AsyncMock(return_value="error: timeout"),
        ),
        patch(
            "app.api.v1.health._ping_seaweedfs",
            new=AsyncMock(return_value="error: HTTP 503"),
        ),
    ):
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["valkey"].startswith("error:")
    assert data["checks"]["seaweedfs"].startswith("error:")
