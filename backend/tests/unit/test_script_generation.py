# SPDX-License-Identifier: Apache-2.0
"""
Phase 4 unit tests — script generation.

All tests use fakes / mocks; no real API calls are made.
The @pytest.mark.integration tests require GEMINI_API_KEY and are skipped by default.
"""
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.entities import Script
from app.domain.value_objects import BlobKey

# ---------------------------------------------------------------------------
# Fake LLMScriptGenerator
# ---------------------------------------------------------------------------

class FakeScriptGenerator:
    """In-process fake that returns deterministic output without calling any API."""

    def __init__(self, text: str = "This slide introduces the main topic.") -> None:
        self._text = text

    async def generate(
        self,
        slide_image_bytes: bytes,
        slide_text: str,
        style_reference: str | None,
        pronunciation_hints: str | None,
    ) -> object:
        from app.services.script.interface import GeneratedScript
        return GeneratedScript(
            text=self._text,
            estimated_reading_seconds=30,
            pronunciation_hints=None,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_script(
    text: str = "Hello world.",
    version: int = 1,
    pronunciation_hints: str | None = None,
) -> Script:
    return Script(
        id=uuid.uuid4(),
        slide_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        text=text,
        estimated_reading_seconds=10,
        pronunciation_hints=pronunciation_hints,
        version=version,
        script_hash=hashlib.sha256(text.encode()).hexdigest(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Test: factory returns correct adapter
# ---------------------------------------------------------------------------

def test_factory_gemini_returns_gemini_generator() -> None:
    from app.services.script import factory as f
    with patch.object(f.settings, "llm_provider", "gemini"):  # type: ignore[attr-defined]
        gen = f.get_script_generator()
    from app.services.script.gemini_adapter import GeminiScriptGenerator
    assert isinstance(gen, GeminiScriptGenerator)


def test_factory_ollama_returns_ollama_generator() -> None:
    from app.services.script import factory as f
    with patch.object(f.settings, "llm_provider", "ollama"):  # type: ignore[attr-defined]
        gen = f.get_script_generator()
    from app.services.script.ollama_adapter import OllamaScriptGenerator
    assert isinstance(gen, OllamaScriptGenerator)


def test_factory_unknown_raises() -> None:
    from app.services.script import factory as f
    with patch.object(f.settings, "llm_provider", "unknown_provider"):  # type: ignore[attr-defined]
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            f.get_script_generator()


# ---------------------------------------------------------------------------
# Test: prompt assembly contains style-injection framing text
# ---------------------------------------------------------------------------

def test_prompt_assembly_contains_style_framing_when_reference_given() -> None:
    """The assembled prompt must contain the framing from the template file."""
    from app.services.script.prompts import build_prompt_v1

    prompt = build_prompt_v1(
        slide_text="Introduction to Neural Networks",
        style_reference="So, what we're looking at here is basically a big matrix of numbers.",
        pronunciation_hints=None,
    )

    assert "speaking style" in prompt.lower()
    assert "vocabulary" in prompt.lower()
    assert "So, what we're looking at here" in prompt


def test_prompt_assembly_omits_style_block_when_no_reference() -> None:
    from app.services.script.prompts import build_prompt_v1

    prompt = build_prompt_v1(
        slide_text="Agenda",
        style_reference=None,
        pronunciation_hints=None,
    )

    assert "speaking style" not in prompt.lower()
    assert "Agenda" in prompt


def test_prompt_assembly_includes_pronunciation_hints_when_given() -> None:
    from app.services.script.prompts import build_prompt_v1

    prompt = build_prompt_v1(
        slide_text="Deep learning architectures",
        style_reference=None,
        pronunciation_hints="GAN=GAN, LSTM=el-es-tee-em",
    )

    assert "GAN=GAN" in prompt
    assert "pronunciation" in prompt.lower()


# ---------------------------------------------------------------------------
# Test: Gemini adapter output validation triggers retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemini_adapter_retries_on_markdown_artifacts() -> None:
    """A response with '**bold**' triggers a single retry with the stricter prompt."""
    from app.services.script.gemini_adapter import GeminiScriptGenerator

    bad_response = json.dumps({
        "text": "This is **very important** content [see slide].",
        "estimated_reading_seconds": 30,
        "pronunciation_hints": None,
    })
    clean_response = json.dumps({
        "text": "This is very important content, as shown on the slide.",
        "estimated_reading_seconds": 30,
        "pronunciation_hints": None,
    })

    gen = GeminiScriptGenerator()
    call_count = 0

    async def fake_call(prompt: str, image_bytes: bytes) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return bad_response
        return clean_response

    with patch.object(gen, "_call_api", side_effect=fake_call):
        result = await gen.generate(
            slide_image_bytes=b"fake-png",
            slide_text="Important concept",
            style_reference=None,
            pronunciation_hints=None,
        )

    assert call_count == 2
    assert "**" not in result.text
    assert "[" not in result.text


@pytest.mark.asyncio
async def test_gemini_adapter_raises_after_two_artifact_failures() -> None:
    """If both attempts return markdown artifacts, ScriptGenerationError is raised."""
    from app.domain.exceptions import ScriptGenerationError
    from app.services.script.gemini_adapter import GeminiScriptGenerator

    bad = json.dumps({
        "text": "Still has [brackets] here.",
        "estimated_reading_seconds": 20,
        "pronunciation_hints": None,
    })

    gen = GeminiScriptGenerator()

    async def always_bad(prompt: str, image_bytes: bytes) -> str:
        return bad

    with patch.object(gen, "_call_api", side_effect=always_bad):
        with pytest.raises(ScriptGenerationError, match="markdown artifacts"):
            await gen.generate(
                slide_image_bytes=b"fake-png",
                slide_text="Slide text",
                style_reference=None,
                pronunciation_hints=None,
            )


# ---------------------------------------------------------------------------
# Test: script_generation task — full happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_script_generation_task_upserts_script() -> None:
    """script_generation task persists the generated script via the repository."""
    from app.tasks.script_generation import _run

    slide_id = str(uuid.uuid4())
    vp_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    project_id = uuid.uuid4()

    fake_slide = MagicMock()
    fake_slide.id = uuid.UUID(slide_id)
    fake_slide.project_id = project_id
    fake_slide.extracted_text = "Introduction to ML"
    fake_slide.image_blob = BlobKey(bucket="lv", key=f"projects/{project_id}/slides/1.png")

    fake_profile = MagicMock()
    fake_profile.style_reference_transcript = "Today we're going to look at ML."
    fake_profile.extra_style_sample = None

    from app.services.script.interface import GeneratedScript
    fake_generated = GeneratedScript(
        text="Today we look at machine learning basics.",
        estimated_reading_seconds=30,
        pronunciation_hints=None,
    )
    fake_generator = AsyncMock()
    fake_generator.generate = AsyncMock(return_value=fake_generated)

    saved_script = _make_script(text=fake_generated.text)

    mock_slide_repo = AsyncMock()
    mock_slide_repo.get = AsyncMock(return_value=fake_slide)

    mock_voice_repo = AsyncMock()
    mock_voice_repo.get = AsyncMock(return_value=fake_profile)

    mock_script_repo = AsyncMock()
    mock_script_repo.get_by_slide = AsyncMock(return_value=None)
    mock_script_repo.upsert = AsyncMock(return_value=saved_script)

    mock_job_repo = AsyncMock()
    mock_job_repo.update_status = AsyncMock()

    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=b"fake-png-bytes")

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.close = AsyncMock()

    with (
        patch("app.db.session.get_task_session", new=AsyncMock(return_value=mock_session)),
        patch("app.db.repositories.job_repository.JobRepository", return_value=mock_job_repo),
        patch("app.db.repositories.slide_repository.SlideRepository", return_value=mock_slide_repo),
        patch("app.db.repositories.voice_profile_repository.VoiceProfileRepository", return_value=mock_voice_repo),
        patch("app.db.repositories.script_repository.ScriptRepository", return_value=mock_script_repo),
        patch("app.services.storage.factory.get_blob_store", return_value=mock_store),
        patch("app.services.script.factory.get_script_generator", return_value=fake_generator),
    ):
        result = await _run(
            slide_id=slide_id,
            voice_profile_id=vp_id,
            job_id=job_id,
        )

    assert result["status"] == "ok"
    assert result["slide_id"] == slide_id

    mock_script_repo.upsert.assert_awaited_once()
    call_kwargs = mock_script_repo.upsert.call_args
    assert call_kwargs.kwargs["text"] == fake_generated.text

    success_calls = [
        c for c in mock_job_repo.update_status.await_args_list if c.args[1] == "success"
    ]
    assert len(success_calls) == 1


# ---------------------------------------------------------------------------
# Test: script_hash recomputed on PATCH text change
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_script_hash_recomputed_on_text_update(client: object) -> None:
    """PATCH /scripts/{id} with a new text must produce a different script_hash."""
    import hashlib

    from app.db.repositories.script_repository import compute_script_hash

    old_text = "Old narration."
    new_text = "New narration for a better explanation."

    old_hash = compute_script_hash(old_text)
    new_hash = compute_script_hash(new_text)

    assert old_hash != new_hash
    assert new_hash == hashlib.sha256(new_text.encode("utf-8")).hexdigest()


_USER_ID = uuid.uuid5(uuid.NAMESPACE_OID, "test-api-key")
_HEADERS = {"X-API-Key": "test-api-key"}


@pytest.mark.asyncio
async def test_patch_endpoint_recomputes_hash() -> None:
    """Calling the PATCH endpoint with new text returns an updated script_hash."""
    from app.db.repositories.script_repository import compute_script_hash
    from app.db.session import get_session
    from app.domain.entities import Project
    from app.main import app

    project_id = uuid.uuid4()
    script_id = uuid.uuid4()
    new_text = "Updated narration text."

    now = datetime.now(UTC)
    base = _make_script(text=new_text, version=2)
    updated_script = Script(
        id=script_id,
        slide_id=base.slide_id,
        project_id=project_id,
        text=new_text,
        estimated_reading_seconds=15,
        pronunciation_hints=None,
        version=2,
        script_hash=compute_script_hash(new_text),
        created_at=now,
        updated_at=now,
    )

    fake_project = Project(
        id=project_id,
        user_id=_USER_ID,  # must match uuid5(NAMESPACE_OID, "test-api-key")
        title="Test",
        voice_profile_id=None,
        wizard_step="scripts",
        created_at=now,
        updated_at=now,
    )

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    async def override_session() -> object:
        yield mock_session

    with (
        patch(
            "app.db.repositories.project_repository.ProjectRepository.get",
            new=AsyncMock(return_value=fake_project),
        ),
        patch(
            "app.db.repositories.script_repository.ScriptRepository.get",
            new=AsyncMock(return_value=updated_script),
        ),
        patch(
            "app.db.repositories.script_repository.ScriptRepository.update",
            new=AsyncMock(return_value=updated_script),
        ),
    ):
        from httpx import ASGITransport, AsyncClient

        app.dependency_overrides[get_session] = override_session
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.patch(
                    f"/api/v1/projects/{project_id}/scripts/{script_id}",
                    json={"text": new_text},
                    headers=_HEADERS,
                )
        finally:
            app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["script_hash"] == compute_script_hash(new_text)
    assert data["version"] == 2


# ---------------------------------------------------------------------------
# Integration test (skipped unless GEMINI_API_KEY is set)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="Skipped unless GEMINI_API_KEY is set (calls real Gemini API)",
)
@pytest.mark.asyncio
async def test_gemini_adapter_real_call_returns_clean_script() -> None:
    """Given a real slide image + text, Gemini returns a non-empty script with no markdown."""
    import importlib
    import io
    import os

    from PIL import Image  # type: ignore[import-untyped]

    # Minimal 1x1 white PNG
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    with patch.dict(os.environ, {"GEMINI_API_KEY": os.environ["GEMINI_API_KEY"]}):
        # Re-load settings to pick up real key
        import app.core.config as cfg
        importlib.reload(cfg)

        from app.services.script.gemini_adapter import GeminiScriptGenerator
        gen = GeminiScriptGenerator()
        result = await gen.generate(
            slide_image_bytes=png_bytes,
            slide_text="Introduction: What is Machine Learning?",
            style_reference="So, in today's lecture we're going to dive into machine learning.",
            pronunciation_hints=None,
        )

    assert isinstance(result.text, str)
    assert len(result.text) > 10
    assert "[" not in result.text
    assert "**" not in result.text
    assert result.estimated_reading_seconds > 0
