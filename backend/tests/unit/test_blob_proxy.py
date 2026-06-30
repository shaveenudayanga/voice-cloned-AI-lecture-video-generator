# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_blob_proxy_png_content_type(client) -> None:
    """PNG blob_key → Content-Type: image/png."""
    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with patch(
        "app.api.v1.blobs.get_blob_store",
        return_value=AsyncMock(get=AsyncMock(return_value=fake_bytes)),
    ):
        response = await client.get(
            "/api/v1/blobs/projects/test-id/slides/slide-1.png",
            headers={"X-API-Key": "test-api-key"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == fake_bytes


@pytest.mark.asyncio
async def test_blob_proxy_wav_content_type(client) -> None:
    """WAV blob_key → Content-Type: audio/wav."""
    fake_bytes = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 50

    with patch(
        "app.api.v1.blobs.get_blob_store",
        return_value=AsyncMock(get=AsyncMock(return_value=fake_bytes)),
    ):
        response = await client.get(
            "/api/v1/blobs/projects/test-id/audio/clip.wav",
            headers={"X-API-Key": "test-api-key"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")


@pytest.mark.asyncio
async def test_blob_proxy_mp4_content_type(client) -> None:
    """MP4 blob_key → Content-Type: video/mp4."""
    fake_bytes = b"\x00\x00\x00\x18ftyp" + b"\x00" * 100

    with patch(
        "app.api.v1.blobs.get_blob_store",
        return_value=AsyncMock(get=AsyncMock(return_value=fake_bytes)),
    ):
        response = await client.get(
            "/api/v1/blobs/projects/test-id/output/video.mp4",
            headers={"X-API-Key": "test-api-key"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")


@pytest.mark.asyncio
async def test_blob_proxy_not_found_returns_404(client) -> None:
    """Storage raises → proxy returns 404, not 500."""
    with patch(
        "app.api.v1.blobs.get_blob_store",
        return_value=AsyncMock(get=AsyncMock(side_effect=Exception("NoSuchKey"))),
    ):
        response = await client.get(
            "/api/v1/blobs/projects/no-such/thing.png",
            headers={"X-API-Key": "test-api-key"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_blob_proxy_requires_auth(client) -> None:
    """No X-API-Key header → 401."""
    response = await client.get("/api/v1/blobs/projects/test/slides/slide.png")
    assert response.status_code == 401
