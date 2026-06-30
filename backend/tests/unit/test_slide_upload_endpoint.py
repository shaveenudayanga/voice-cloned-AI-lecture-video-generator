# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for POST /api/v1/projects/{project_id}/slides/upload and GET /api/v1/jobs/{job_id}.

Storage calls and Celery tasks are mocked; no real DB or S3 needed.
FastAPI dependency overrides replace the DB session with an AsyncMock.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

FIXTURES = Path(__file__).parent.parent / "fixtures"
PROJECT_ID = str(uuid.uuid4())
PPTX_CTYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
HEADERS = {"X-API-Key": "test-api-key"}


def _make_mock_job(job_id: uuid.UUID | None = None) -> MagicMock:
    mock_job = MagicMock()
    mock_job.id = job_id or uuid.uuid4()
    mock_job.task_name = "slide_ingestion"
    mock_job.status = "queued"
    mock_job.progress_pct = 0
    mock_job.result_payload = None
    mock_job.error_message = None
    mock_job.related_entity_id = uuid.UUID(PROJECT_ID)
    mock_job.created_at = datetime.now(UTC)
    mock_job.updated_at = datetime.now(UTC)
    return mock_job


def _make_mock_session(job_id: uuid.UUID | None = None) -> AsyncMock:
    """Return an async session mock wired up with realistic repository stubs."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    mock_job = _make_mock_job(job_id)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = mock_job
    session.execute = AsyncMock(return_value=mock_result)

    return session


@pytest.fixture
async def upload_client():
    """App client with mocked session for upload endpoint tests."""
    from app.db.session import get_session
    from app.main import app

    mock_session = _make_mock_session()

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
async def job_not_found_client():
    """App client where job lookup returns None."""
    from app.db.session import get_session
    from app.main import app

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_upload_pdf_returns_202(upload_client) -> None:
    pdf_bytes = (FIXTURES / "sample_3page.pdf").read_bytes()

    with (
        patch("app.api.v1.slides.get_blob_store") as mock_store_factory,
        patch("app.api.v1.slides.ingest_slides") as mock_task,
    ):
        mock_store = AsyncMock()
        mock_store.ensure_bucket = AsyncMock()
        mock_store.put = AsyncMock(return_value="projects/.../source/test.pdf")
        mock_store_factory.return_value = mock_store
        mock_task.delay = MagicMock()

        response = await upload_client.post(
            f"/api/v1/projects/{PROJECT_ID}/slides/upload",
            headers=HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["project_id"] == PROJECT_ID
    assert "job_id" in body


@pytest.mark.asyncio
async def test_upload_rejects_over_size_limit(upload_client) -> None:
    from app.core.config import settings

    oversized = b"A" * (settings.max_upload_bytes + 1)

    with patch("app.api.v1.slides.get_blob_store"):
        response = await upload_client.post(
            f"/api/v1/projects/{PROJECT_ID}/slides/upload",
            headers=HEADERS,
            files={"file": ("big.pdf", oversized, "application/pdf")},
        )

    assert response.status_code == 413, response.text


@pytest.mark.asyncio
async def test_upload_rejects_exe_renamed_to_pdf(upload_client) -> None:
    """A file with PDF Content-Type but EXE magic bytes must be rejected with 415."""
    fake_exe = b"MZ\x00\x00\x00\x00\x00\x00" + b"A" * 100

    with patch("app.api.v1.slides.get_blob_store"):
        response = await upload_client.post(
            f"/api/v1/projects/{PROJECT_ID}/slides/upload",
            headers=HEADERS,
            files={"file": ("evil.pdf", fake_exe, "application/pdf")},
        )

    assert response.status_code == 415, response.text


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_mime(upload_client) -> None:
    """A plain text file should be rejected with 415."""
    with patch("app.api.v1.slides.get_blob_store"):
        response = await upload_client.post(
            f"/api/v1/projects/{PROJECT_ID}/slides/upload",
            headers=HEADERS,
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )

    assert response.status_code == 415, response.text


@pytest.mark.asyncio
async def test_job_not_found_returns_404(job_not_found_client) -> None:
    fake_id = str(uuid.uuid4())
    response = await job_not_found_client.get(f"/api/v1/jobs/{fake_id}", headers=HEADERS)
    assert response.status_code == 404, response.text
