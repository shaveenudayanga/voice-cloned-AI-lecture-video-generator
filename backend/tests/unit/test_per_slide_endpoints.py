# SPDX-License-Identifier: Apache-2.0
"""
Phase 8 unit tests — per-slide script regeneration and audio synthesis endpoints.

All DB and Celery calls are mocked; no real services needed.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

HEADERS = {"X-API-Key": "test-api-key"}
_USER_ID = uuid.uuid5(uuid.NAMESPACE_OID, "test-api-key")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_project(
    project_id: uuid.UUID | None = None,
    voice_profile_id: uuid.UUID | None = None,
) -> MagicMock:
    m = MagicMock()
    m.id = project_id or uuid.uuid4()
    m.user_id = _USER_ID
    m.title = "Test Lecture"
    m.voice_profile_id = voice_profile_id
    m.wizard_step = "scripts"
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


def _mock_slide(
    slide_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    order_index: int = 0,
) -> MagicMock:
    m = MagicMock()
    m.id = slide_id or uuid.uuid4()
    m.project_id = project_id or uuid.uuid4()
    m.order_index = order_index
    m.image_blob.bucket = "lecturevoice"
    m.image_blob.key = f"projects/{m.project_id}/slides/{order_index}.png"
    m.extracted_text = "Slide content"
    m.created_at = datetime.now(UTC)
    return m


def _mock_script(
    script_id: uuid.UUID | None = None,
    slide_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> MagicMock:
    m = MagicMock()
    m.id = script_id or uuid.uuid4()
    m.slide_id = slide_id or uuid.uuid4()
    m.project_id = project_id or uuid.uuid4()
    m.text = "This slide introduces the topic."
    m.estimated_reading_seconds = 20
    m.pronunciation_hints = None
    m.version = 1
    m.script_hash = "abc123"
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


def _mock_job(task_name: str = "script_generation") -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.task_name = task_name
    m.status = "queued"
    m.progress_pct = 0
    m.result_payload = None
    m.error_message = None
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


def _make_session() -> AsyncMock:
    s = AsyncMock()
    s.commit = AsyncMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    return s


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/scripts/{slide_id}/regenerate → 202
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regenerate_slide_script_returns_202() -> None:
    """Enqueues a single script_generation job and returns 202 with job_id and slide_id."""
    from app.db.session import get_session
    from app.main import app

    project_id = uuid.uuid4()
    slide_id = uuid.uuid4()
    voice_profile_id = uuid.uuid4()

    project = _mock_project(project_id=project_id, voice_profile_id=voice_profile_id)
    slide = _mock_slide(slide_id=slide_id, project_id=project_id)
    job = _mock_job()

    session = _make_session()

    async def override_session() -> object:
        yield session

    with (
        patch(
            "app.db.repositories.project_repository.ProjectRepository.get",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.db.repositories.slide_repository.SlideRepository.get",
            new=AsyncMock(return_value=slide),
        ),
        patch(
            "app.db.repositories.job_repository.JobRepository.create",
            new=AsyncMock(return_value=job),
        ),
        patch("app.api.v1.scripts.generate_script") as mock_task,
    ):
        mock_task.delay = MagicMock()
        app.dependency_overrides[get_session] = override_session
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    f"/api/v1/projects/{project_id}/scripts/{slide_id}/regenerate",
                    headers=HEADERS,
                )
        finally:
            app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["slide_id"] == str(slide_id)
    assert "job_id" in body
    mock_task.delay.assert_called_once()


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/scripts/{slide_id}/regenerate → 404
# when slide does not belong to this project
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regenerate_slide_script_404_slide_not_in_project() -> None:
    """Returns 404 when the slide belongs to a different project."""
    from app.db.session import get_session
    from app.main import app

    project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    slide_id = uuid.uuid4()
    voice_profile_id = uuid.uuid4()

    project = _mock_project(project_id=project_id, voice_profile_id=voice_profile_id)
    # Slide belongs to a DIFFERENT project
    slide = _mock_slide(slide_id=slide_id, project_id=other_project_id)

    session = _make_session()

    async def override_session() -> object:
        yield session

    with (
        patch(
            "app.db.repositories.project_repository.ProjectRepository.get",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.db.repositories.slide_repository.SlideRepository.get",
            new=AsyncMock(return_value=slide),
        ),
    ):
        app.dependency_overrides[get_session] = override_session
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    f"/api/v1/projects/{project_id}/scripts/{slide_id}/regenerate",
                    headers=HEADERS,
                )
        finally:
            app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/scripts/{slide_id}/regenerate → 422
# when project has no voice_profile_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regenerate_slide_script_422_no_voice_profile() -> None:
    """Returns 422 when the project has no voice_profile_id set."""
    from app.db.session import get_session
    from app.main import app

    project_id = uuid.uuid4()
    slide_id = uuid.uuid4()

    # Project with NO voice_profile_id
    project = _mock_project(project_id=project_id, voice_profile_id=None)

    session = _make_session()

    async def override_session() -> object:
        yield session

    with patch(
        "app.db.repositories.project_repository.ProjectRepository.get",
        new=AsyncMock(return_value=project),
    ):
        app.dependency_overrides[get_session] = override_session
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    f"/api/v1/projects/{project_id}/scripts/{slide_id}/regenerate",
                    headers=HEADERS,
                )
        finally:
            app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 422, resp.text
    assert "VoiceProfile" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/audio/{slide_id}/synthesize → 202
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesize_slide_audio_returns_202() -> None:
    """Enqueues a single tts_synthesis job and returns 202 with job_id and slide_id."""
    from app.db.session import get_session
    from app.main import app

    project_id = uuid.uuid4()
    slide_id = uuid.uuid4()
    voice_profile_id = uuid.uuid4()

    project = _mock_project(project_id=project_id, voice_profile_id=voice_profile_id)
    slide = _mock_slide(slide_id=slide_id, project_id=project_id)
    script = _mock_script(slide_id=slide_id, project_id=project_id)
    job = _mock_job(task_name="tts_synthesis")

    session = _make_session()

    async def override_session() -> object:
        yield session

    with (
        patch(
            "app.db.repositories.project_repository.ProjectRepository.get",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.db.repositories.slide_repository.SlideRepository.get",
            new=AsyncMock(return_value=slide),
        ),
        patch(
            "app.db.repositories.script_repository.ScriptRepository.get_by_slide",
            new=AsyncMock(return_value=script),
        ),
        patch(
            "app.db.repositories.job_repository.JobRepository.create",
            new=AsyncMock(return_value=job),
        ),
        patch("app.api.v1.audio.synthesize_slide") as mock_task,
    ):
        mock_task.delay = MagicMock()
        app.dependency_overrides[get_session] = override_session
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    f"/api/v1/projects/{project_id}/audio/{slide_id}/synthesize",
                    headers=HEADERS,
                )
        finally:
            app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["slide_id"] == str(slide_id)
    assert "job_id" in body
    mock_task.delay.assert_called_once()


# ---------------------------------------------------------------------------
# POST /projects/{project_id}/audio/{slide_id}/synthesize → 422
# when slide has no script
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesize_slide_audio_422_no_script() -> None:
    """Returns 422 when the slide has no associated script."""
    from app.db.session import get_session
    from app.main import app

    project_id = uuid.uuid4()
    slide_id = uuid.uuid4()
    voice_profile_id = uuid.uuid4()

    project = _mock_project(project_id=project_id, voice_profile_id=voice_profile_id)
    slide = _mock_slide(slide_id=slide_id, project_id=project_id)

    session = _make_session()

    async def override_session() -> object:
        yield session

    with (
        patch(
            "app.db.repositories.project_repository.ProjectRepository.get",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.db.repositories.slide_repository.SlideRepository.get",
            new=AsyncMock(return_value=slide),
        ),
        patch(
            "app.db.repositories.script_repository.ScriptRepository.get_by_slide",
            new=AsyncMock(return_value=None),  # No script
        ),
    ):
        app.dependency_overrides[get_session] = override_session
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    f"/api/v1/projects/{project_id}/audio/{slide_id}/synthesize",
                    headers=HEADERS,
                )
        finally:
            app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 422, resp.text
    assert "script" in resp.json()["detail"].lower()
