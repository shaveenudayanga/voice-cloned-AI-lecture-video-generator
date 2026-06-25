# SPDX-License-Identifier: Apache-2.0
import pytest


@pytest.mark.asyncio
async def test_missing_api_key_returns_401(client) -> None:
    response = await client.get("/api/v1/projects")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_api_key_is_accepted(client) -> None:
    response = await client.get(
        "/api/v1/projects",
        headers={"X-API-Key": "test-api-key"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_wrong_api_key_returns_401(client) -> None:
    response = await client.get(
        "/api/v1/projects",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401
