# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Phase 3 — Voice Profiles & Transcription.

Storage, Celery tasks, and DB repositories are mocked throughout.
No real network or model calls are made in these tests.
"""
import io
import uuid
import wave
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

HEADERS = {"X-API-Key": "test-api-key"}
_USER_ID = uuid.uuid5(uuid.NAMESPACE_OID, "test-api-key")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_wav_bytes(duration_s: float = 1.0) -> bytes:
    """Generate a valid WAV file in memory using pure stdlib (no extra deps)."""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


@pytest.fixture
def wav_bytes() -> bytes:
    return make_wav_bytes(1.0)


def _mock_profile(
    profile_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    display_name: str = "Test Voice",
    is_default: bool = False,
    transcript: str = "",
) -> MagicMock:
    m = MagicMock()
    m.id = profile_id or uuid.uuid4()
    m.user_id = user_id or _USER_ID
    m.display_name = display_name
    m.style_reference_transcript = transcript
    m.extra_style_sample = None
    m.is_default = is_default
    m.tts_engine = "f5"
    m.tts_params = {}
    m.audio_blob.bucket = "lecturevoice"
    m.audio_blob.key = "users/x/voices/y.wav"
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


def _mock_project(
    project_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    title: str = "My Lecture",
    voice_profile_id: uuid.UUID | None = None,
) -> MagicMock:
    m = MagicMock()
    m.id = project_id or uuid.uuid4()
    m.user_id = user_id or _USER_ID
    m.title = title
    m.voice_profile_id = voice_profile_id
    m.wizard_step = "upload"
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


def _mock_job(task_name: str = "voice_ingestion") -> MagicMock:
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


# ---------------------------------------------------------------------------
# POST /api/v1/voices/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_voice_profile_returns_202(wav_bytes: bytes) -> None:
    """Valid WAV upload returns 202 with profile_id, job_id, status=queued."""
    from app.db.session import get_session
    from app.main import app

    session = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    async def override_session() -> AsyncMock:
        yield session  # type: ignore[misc]

    app.dependency_overrides[get_session] = override_session

    profile = _mock_profile()
    ingest_job = _mock_job("voice_ingestion")
    preview_job = _mock_job("voice_preview")

    try:
        with (
            patch("app.api.v1.voices.VoiceProfileRepository") as mock_vp_repo_cls,
            patch("app.api.v1.voices.JobRepository") as mock_job_repo_cls,
            patch("app.api.v1.voices.get_blob_store") as mock_store_factory,
            patch("app.api.v1.voices.ingest_voice") as mock_ingest,
            patch("app.api.v1.voices.synthesize_preview") as mock_preview,
        ):
            vp_repo = mock_vp_repo_cls.return_value
            vp_repo.count_by_user = AsyncMock(return_value=0)
            vp_repo.create = AsyncMock(return_value=profile)

            job_repo = mock_job_repo_cls.return_value
            job_repo.create = AsyncMock(side_effect=[ingest_job, preview_job])

            mock_store = AsyncMock()
            mock_store.ensure_bucket = AsyncMock()
            mock_store.put = AsyncMock(return_value="key")
            mock_store_factory.return_value = mock_store
            mock_ingest.delay = MagicMock()
            mock_preview.delay = MagicMock()

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.post(
                    "/api/v1/voices",
                    headers=HEADERS,
                    data={"display_name": "Prof Voice"},
                    files={"file": ("recording.wav", wav_bytes, "audio/wav")},
                )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 202, response.text
    body = response.json()
    assert "profile_id" in body
    assert "job_id" in body
    assert body["status"] == "queued"
    mock_ingest.delay.assert_called_once()
    mock_preview.delay.assert_called_once()


@pytest.mark.asyncio
async def test_create_voice_profile_rejects_text_file() -> None:
    """A text/plain file must be rejected with 415."""
    from app.db.session import get_session
    from app.main import app

    session = AsyncMock()

    async def override_session() -> AsyncMock:
        yield session  # type: ignore[misc]

    app.dependency_overrides[get_session] = override_session

    try:
        with patch("app.api.v1.voices.get_blob_store"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.post(
                    "/api/v1/voices",
                    headers=HEADERS,
                    data={"display_name": "Prof Voice"},
                    files={"file": ("notes.txt", b"hello world", "text/plain")},
                )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 415, response.text


@pytest.mark.asyncio
async def test_create_voice_profile_rejects_oversized() -> None:
    """File exceeding max_voice_upload_mb must be rejected with 413."""
    from app.api.v1.voices import settings as voice_settings
    from app.db.session import get_session
    from app.main import app

    session = AsyncMock()

    async def override_session() -> AsyncMock:
        yield session  # type: ignore[misc]

    app.dependency_overrides[get_session] = override_session

    oversized = b"A" * (voice_settings.max_voice_upload_mb * 1024 * 1024 + 1)
    try:
        with patch("app.api.v1.voices.get_blob_store"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.post(
                    "/api/v1/voices",
                    headers=HEADERS,
                    data={"display_name": "Prof Voice"},
                    files={"file": ("big.wav", oversized, "audio/wav")},
                )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 413, response.text


# ---------------------------------------------------------------------------
# GET /api/v1/voices/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_voice_profiles_empty() -> None:
    """Returns an empty list when the user has no profiles."""
    from app.db.session import get_session
    from app.main import app

    session = AsyncMock()

    async def override_session() -> AsyncMock:
        yield session  # type: ignore[misc]

    app.dependency_overrides[get_session] = override_session

    try:
        with patch("app.api.v1.voices.VoiceProfileRepository") as mock_vp_repo_cls:
            mock_vp_repo_cls.return_value.list_by_user = AsyncMock(return_value=[])

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.get("/api/v1/voices", headers=HEADERS)
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_voice_profiles_returns_summaries() -> None:
    """Returns a list of VoiceProfileSummary objects."""
    from app.db.session import get_session
    from app.main import app

    session = AsyncMock()

    async def override_session() -> AsyncMock:
        yield session  # type: ignore[misc]

    app.dependency_overrides[get_session] = override_session
    profile = _mock_profile(transcript="Hello world from the professor")

    try:
        with patch("app.api.v1.voices.VoiceProfileRepository") as mock_vp_repo_cls:
            mock_vp_repo_cls.return_value.list_by_user = AsyncMock(return_value=[profile])

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.get("/api/v1/voices", headers=HEADERS)
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["has_transcript"] is True
    assert data[0]["display_name"] == "Test Voice"


# ---------------------------------------------------------------------------
# PATCH /api/v1/voices/{profile_id} — is_default logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_set_default_unsets_previous() -> None:
    """Setting is_default=True on a second profile must call unset_default_for_user first."""
    from app.db.session import get_session
    from app.main import app

    session = AsyncMock()

    async def override_session() -> AsyncMock:
        yield session  # type: ignore[misc]

    app.dependency_overrides[get_session] = override_session

    profile_id = uuid.uuid4()
    original = _mock_profile(profile_id=profile_id, is_default=False)
    updated = _mock_profile(profile_id=profile_id, is_default=True)

    try:
        with patch("app.api.v1.voices.VoiceProfileRepository") as mock_vp_repo_cls:
            vp_repo = mock_vp_repo_cls.return_value
            vp_repo.get = AsyncMock(return_value=original)
            vp_repo.unset_default_for_user = AsyncMock()
            vp_repo.update = AsyncMock(return_value=updated)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.patch(
                    f"/api/v1/voices/{profile_id}",
                    headers=HEADERS,
                    json={"is_default": True},
                )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200, response.text
    # unset_default_for_user must have been called before setting the new default
    vp_repo.unset_default_for_user.assert_awaited_once_with(_USER_ID)
    assert response.json()["is_default"] is True


# ---------------------------------------------------------------------------
# DELETE /api/v1/voices/{profile_id} — 409 when project references it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_voice_profile_409_when_project_references_it() -> None:
    """DELETE must return 409 if any project still has voice_profile_id set to this profile."""
    from app.db.session import get_session
    from app.main import app

    session = AsyncMock()

    async def override_session() -> AsyncMock:
        yield session  # type: ignore[misc]

    app.dependency_overrides[get_session] = override_session

    profile_id = uuid.uuid4()
    profile = _mock_profile(profile_id=profile_id)
    project = _mock_project(voice_profile_id=profile_id, title="Intro to ML")

    try:
        with (
            patch("app.api.v1.voices.VoiceProfileRepository") as mock_vp_repo_cls,
            patch("app.api.v1.voices.ProjectRepository") as mock_proj_repo_cls,
        ):
            mock_vp_repo_cls.return_value.get = AsyncMock(return_value=profile)
            mock_proj_repo_cls.return_value.list_by_voice_profile = AsyncMock(return_value=[project])

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.delete(f"/api/v1/voices/{profile_id}", headers=HEADERS)
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 409, response.text
    assert "Intro to ML" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_voice_profile_204_when_no_project_references_it() -> None:
    """DELETE succeeds with 204 when no project references the profile."""
    from app.db.session import get_session
    from app.main import app

    session = AsyncMock()

    async def override_session() -> AsyncMock:
        yield session  # type: ignore[misc]

    app.dependency_overrides[get_session] = override_session

    profile_id = uuid.uuid4()
    profile = _mock_profile(profile_id=profile_id)

    try:
        with (
            patch("app.api.v1.voices.VoiceProfileRepository") as mock_vp_repo_cls,
            patch("app.api.v1.voices.ProjectRepository") as mock_proj_repo_cls,
            patch("app.api.v1.voices.get_blob_store") as mock_store_factory,
        ):
            vp_repo = mock_vp_repo_cls.return_value
            vp_repo.get = AsyncMock(return_value=profile)
            vp_repo.delete = AsyncMock()

            mock_proj_repo_cls.return_value.list_by_voice_profile = AsyncMock(return_value=[])

            mock_store = AsyncMock()
            mock_store.delete = AsyncMock()
            mock_store_factory.return_value = mock_store

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.delete(f"/api/v1/voices/{profile_id}", headers=HEADERS)
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 204, response.text
    vp_repo.delete.assert_awaited_once_with(profile_id)


# ---------------------------------------------------------------------------
# ADR-0009: VoiceProfile is user-owned, reusable across projects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adr_0009_existing_voice_profile_reusable_across_projects() -> None:
    """
    # ADR-0009: VoiceProfile is user-owned, reusable across projects.

    A second project must be able to adopt an existing VoiceProfile via
    PATCH /projects/{id} without any re-recording. The profile.user_id check
    ensures cross-user reuse is blocked while same-user reuse is always allowed.
    """
    from app.db.session import get_session
    from app.main import app

    session = AsyncMock()

    async def override_session() -> AsyncMock:
        yield session  # type: ignore[misc]

    app.dependency_overrides[get_session] = override_session

    profile_id = uuid.uuid4()
    project2_id = uuid.uuid4()

    # Existing VoiceProfile owned by the same user
    existing_profile = _mock_profile(profile_id=profile_id)
    # Second project, initially with no voice profile
    project2_initial = _mock_project(project_id=project2_id, voice_profile_id=None)
    # Project after patching — now has the existing voice profile
    project2_updated = _mock_project(project_id=project2_id, voice_profile_id=profile_id)

    try:
        with (
            patch("app.api.v1.projects.ProjectRepository") as mock_proj_repo_cls,
            patch("app.api.v1.projects.VoiceProfileRepository") as mock_vp_repo_cls,
        ):
            proj_repo = mock_proj_repo_cls.return_value
            proj_repo.get = AsyncMock(return_value=project2_initial)
            proj_repo.update_voice_profile = AsyncMock(return_value=project2_updated)

            vp_repo = mock_vp_repo_cls.return_value
            vp_repo.get = AsyncMock(return_value=existing_profile)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.patch(
                    f"/api/v1/projects/{project2_id}",
                    headers=HEADERS,
                    json={"voice_profile_id": str(profile_id)},
                )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200, response.text
    body = response.json()
    # The second project now references the existing profile — no re-recording needed
    assert body["voice_profile_id"] == str(profile_id)
    proj_repo.update_voice_profile.assert_awaited_once_with(project2_id, profile_id)
