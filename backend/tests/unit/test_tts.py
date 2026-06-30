# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Phase 5: TTS engine, model_manager, synthesis fingerprint, cache-skip.

GPU and slow-model tests are gated behind @pytest.mark.slow and require RUN_SLOW_TESTS=1.
All tests here run without any GPU or real model dependencies.
"""

import io
import os
import uuid
import wave
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wav_bytes(duration_s: float = 1.0) -> bytes:
    sample_rate = 16000
    num_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


def _write_wav(path: Path, duration_s: float = 1.0) -> None:
    path.write_bytes(_make_wav_bytes(duration_s))


# ---------------------------------------------------------------------------
# synthesis_fingerprint
# ---------------------------------------------------------------------------


def test_synthesis_fingerprint_deterministic() -> None:
    """Same inputs always produce the same fingerprint."""
    from app.db.repositories.audio_clip_repository import compute_synthesis_fingerprint

    fp1 = compute_synthesis_fingerprint(
        script_hash="abc123",
        voice_profile_id="profile-1",
        tts_engine="f5",
        tts_params={"speed": 1.0},
    )
    fp2 = compute_synthesis_fingerprint(
        script_hash="abc123",
        voice_profile_id="profile-1",
        tts_engine="f5",
        tts_params={"speed": 1.0},
    )
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex


def test_synthesis_fingerprint_different_script_hash() -> None:
    """A changed script_hash must produce a different fingerprint."""
    from app.db.repositories.audio_clip_repository import compute_synthesis_fingerprint

    fp1 = compute_synthesis_fingerprint("hash-A", "vp1", "f5", {})
    fp2 = compute_synthesis_fingerprint("hash-B", "vp1", "f5", {})
    assert fp1 != fp2


def test_synthesis_fingerprint_different_voice_profile() -> None:
    """A changed voice_profile_id must produce a different fingerprint."""
    from app.db.repositories.audio_clip_repository import compute_synthesis_fingerprint

    fp1 = compute_synthesis_fingerprint("hashX", "voice-1", "f5", {})
    fp2 = compute_synthesis_fingerprint("hashX", "voice-2", "f5", {})
    assert fp1 != fp2


def test_synthesis_fingerprint_params_order_independent() -> None:
    """tts_params with different key order must give the same fingerprint (sort_keys=True)."""
    from app.db.repositories.audio_clip_repository import compute_synthesis_fingerprint

    fp1 = compute_synthesis_fingerprint("h", "v", "f5", {"a": 1, "b": 2})
    fp2 = compute_synthesis_fingerprint("h", "v", "f5", {"b": 2, "a": 1})
    assert fp1 == fp2


# ---------------------------------------------------------------------------
# cache-skip in tts_synthesis task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tts_synthesis_cache_skip_skips_engine() -> None:
    """When an AudioClip with matching fingerprint already exists, the TTS engine
    must NOT be called and the job is immediately marked success."""
    from app.db.repositories.audio_clip_repository import compute_synthesis_fingerprint
    from app.domain.entities import AudioClip, Script, Slide, VoiceProfile
    from app.domain.value_objects import BlobKey
    from app.tasks.tts_synthesis import _run

    slide_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    voice_profile_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    # Build a stub fingerprint that will match the existing clip
    fingerprint = compute_synthesis_fingerprint("script-hash-1", voice_profile_id, "f5", {})

    mock_slide = Slide(
        id=uuid.UUID(slide_id),
        project_id=uuid.UUID(project_id),
        order_index=0,
        image_blob=BlobKey(bucket="b", key="k"),
        extracted_text="text",
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    mock_script = Script(
        id=uuid.uuid4(),
        slide_id=uuid.UUID(slide_id),
        project_id=uuid.UUID(project_id),
        text="Hello world",
        estimated_reading_seconds=5,
        pronunciation_hints=None,
        version=1,
        script_hash="script-hash-1",
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    mock_voice: VoiceProfile = MagicMock(spec=VoiceProfile)
    mock_voice.tts_engine = "f5"
    mock_voice.tts_params = {}
    mock_voice.audio_blob = BlobKey(bucket="b", key="voice.wav")

    existing_clip = AudioClip(
        id=uuid.uuid4(),
        project_id=uuid.UUID(project_id),
        slide_id=uuid.UUID(slide_id),
        script_id=mock_script.id,
        voice_profile_id=uuid.UUID(voice_profile_id),
        audio_blob=BlobKey(bucket="b", key="audio.wav"),
        duration_seconds=5.0,
        engine_used="f5",
        synthesis_fingerprint=fingerprint,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.close = AsyncMock()

    mock_job_repo = AsyncMock()
    mock_slide_repo = AsyncMock()
    mock_slide_repo.get = AsyncMock(return_value=mock_slide)
    mock_script_repo = AsyncMock()
    mock_script_repo.get_by_slide = AsyncMock(return_value=mock_script)
    mock_voice_repo = AsyncMock()
    mock_voice_repo.get = AsyncMock(return_value=mock_voice)
    mock_clip_repo = AsyncMock()
    mock_clip_repo.get_by_fingerprint = AsyncMock(return_value=existing_clip)

    mock_tts_engine = AsyncMock()

    with (
        patch("app.db.session.get_task_session", new=AsyncMock(return_value=mock_session)),
        patch("app.db.repositories.job_repository.JobRepository", return_value=mock_job_repo),
        patch("app.db.repositories.slide_repository.SlideRepository", return_value=mock_slide_repo),
        patch("app.db.repositories.script_repository.ScriptRepository", return_value=mock_script_repo),
        patch("app.db.repositories.voice_profile_repository.VoiceProfileRepository", return_value=mock_voice_repo),
        patch("app.db.repositories.audio_clip_repository.AudioClipRepository", return_value=mock_clip_repo),
        patch("app.services.storage.factory.get_blob_store", return_value=AsyncMock()),
        patch("app.services.tts.factory.get_tts_engine_with_fallback", return_value=mock_tts_engine),
    ):
        result = await _run(
            slide_id=slide_id,
            project_id=project_id,
            voice_profile_id=voice_profile_id,
            job_id=job_id,
        )

    assert result["cache_hit"] is True
    # TTS engine synthesize must NOT have been called
    mock_tts_engine.synthesize.assert_not_called()
    # Job must have been marked success
    success_calls = [c for c in mock_job_repo.update_status.await_args_list if "success" in c.args]
    assert len(success_calls) == 1


# ---------------------------------------------------------------------------
# CUDA OOM → CPU fallback
# ---------------------------------------------------------------------------


def test_f5_oom_triggers_cpu_fallback(tmp_path: Path) -> None:
    """When F5-TTS raises an OOM-classified error, the adapter retries synthesis on CPU.

    Torch and f5_tts are not installed in the dev venv; this test patches sys.modules
    to inject fake implementations and verifies the branching logic (used_gpu=False).
    """
    import sys

    from app.services.tts.f5_adapter import F5TTSAdapter

    ref_path = tmp_path / "ref.wav"
    out_path = tmp_path / "out.wav"
    _write_wav(ref_path)

    infer_call_count = [0]

    def fake_infer_gpu(**kwargs: Any) -> None:
        infer_call_count[0] += 1
        raise RuntimeError("CUDA out of memory (simulated)")

    def fake_infer_cpu(**kwargs: Any) -> None:
        _write_wav(Path(kwargs["file_wave"]))

    fake_gpu_model = MagicMock(name="gpu_model")
    fake_gpu_model.infer = fake_infer_gpu

    fake_cpu_model = MagicMock(name="cpu_model")
    fake_cpu_model.infer = fake_infer_cpu

    # Fake F5TTS class: first call raises (simulates GPU load), second returns cpu model
    fake_f5tts_cls = MagicMock(return_value=fake_cpu_model)

    # Inject fake torch and f5_tts modules so imports inside the fallback path succeed
    fake_torch = MagicMock(name="torch")
    fake_torch.float32 = "float32"
    fake_torch.cuda.OutOfMemoryError = RuntimeError  # map OOM to RuntimeError for _is_oom

    fake_f5_module = MagicMock(name="f5_tts.api")
    fake_f5_module.F5TTS = fake_f5tts_cls

    fake_f5_pkg = MagicMock(name="f5_tts")
    fake_f5_pkg.api = fake_f5_module

    extra_modules = {
        "torch": fake_torch,
        "f5_tts": fake_f5_pkg,
        "f5_tts.api": fake_f5_module,
    }

    import asyncio

    adapter = F5TTSAdapter()

    with patch.dict(sys.modules, extra_modules):
        with (
            patch("app.services.tts.model_manager.load_tts_model", return_value=fake_gpu_model),
            patch("app.services.tts.model_manager.get_vram_free_gb", return_value=0.1),
            patch("app.services.tts.f5_adapter._is_cuda", return_value=True),
            # Make _is_oom return True for our RuntimeError
            patch("app.services.tts.f5_adapter._is_oom", return_value=True),
        ):
            result = asyncio.run(
                adapter.synthesize(
                    text="test",
                    reference_audio_path=ref_path,
                    output_path=out_path,
                )
            )

    assert result.used_gpu is False, "CPU fallback must set used_gpu=False"
    assert infer_call_count[0] == 1, "GPU model infer must be called once (then OOM)"
    assert out_path.exists(), "CPU fallback must write output WAV"


# ---------------------------------------------------------------------------
# model_manager — eviction logic
# ---------------------------------------------------------------------------


def test_model_manager_evicts_tts_before_loading_whisper_on_4gb() -> None:
    """On a 4 GB VRAM budget, loading Whisper after TTS must evict TTS first."""
    import app.services.tts.model_manager as mm

    # Save original state and restore after
    original_tts = mm._tts_model
    original_whisper = mm._whisper_model
    original_owner = mm._tts_slot_owner

    try:
        # Seed: TTS is already loaded, Whisper is not
        mm._tts_model = MagicMock(name="fake_tts_model")
        mm._whisper_model = None
        mm._tts_slot_owner = "f5"

        fake_whisper = MagicMock(name="fake_whisper_model")
        evicted_tts: list[bool] = []

        def fake_load_whisper() -> MagicMock:
            # At the time this runs, TTS must already be evicted
            evicted_tts.append(mm._tts_model is None)
            return fake_whisper

        with (
            patch.object(mm, "_load_whisper", side_effect=fake_load_whisper),
            patch("app.services.tts.model_manager.settings") as mock_settings,
        ):
            mock_settings.vram_budget_gb = 4.0
            mock_settings.whisper_model_size = "base"

            result = mm.load_whisper_model()

        assert result is fake_whisper
        assert evicted_tts == [True], "TTS was not evicted before Whisper loaded on 4 GB budget"
        assert mm._tts_model is None, "TTS should remain evicted after Whisper loaded"

    finally:
        mm._tts_model = original_tts
        mm._whisper_model = original_whisper
        mm._tts_slot_owner = original_owner


def test_model_manager_does_not_evict_on_high_vram() -> None:
    """On >= 6 GB VRAM budget, loading Whisper must NOT evict TTS."""
    import app.services.tts.model_manager as mm

    original_tts = mm._tts_model
    original_whisper = mm._whisper_model
    original_owner = mm._tts_slot_owner

    try:
        mm._tts_model = MagicMock(name="fake_tts_model")
        mm._whisper_model = None
        mm._tts_slot_owner = "f5"

        evicted_tts: list[bool] = []

        def fake_load_whisper() -> MagicMock:
            evicted_tts.append(mm._tts_model is None)
            return MagicMock(name="fake_whisper_model")

        with (
            patch.object(mm, "_load_whisper", side_effect=fake_load_whisper),
            patch("app.services.tts.model_manager.settings") as mock_settings,
        ):
            mock_settings.vram_budget_gb = 12.0
            mock_settings.whisper_model_size = "base"

            mm.load_whisper_model()

        assert evicted_tts == [False], "TTS should NOT be evicted on >= 6 GB VRAM budget"
        assert mm._tts_model is not None, "TTS model must remain after Whisper loaded on 12 GB"

    finally:
        mm._tts_model = original_tts
        mm._whisper_model = original_whisper
        mm._tts_slot_owner = original_owner


def test_model_manager_idempotent_load() -> None:
    """load_tts_model() called twice must not invoke _load_f5 twice."""
    import app.services.tts.model_manager as mm

    original_tts = mm._tts_model
    original_owner = mm._tts_slot_owner

    try:
        mm._tts_model = None
        mm._tts_slot_owner = None
        mm._whisper_model = None

        fake_model = MagicMock(name="fake_f5")
        load_count = [0]

        def fake_load_f5() -> MagicMock:
            load_count[0] += 1
            return fake_model

        with (
            patch.object(mm, "_load_f5", side_effect=fake_load_f5),
            patch("app.services.tts.model_manager.settings") as mock_settings,
            patch("app.services.tts.model_manager.get_vram_free_gb", return_value=4.0),
        ):
            mock_settings.vram_budget_gb = 4.0
            mock_settings.tts_engine = "f5"

            r1 = mm.load_tts_model()
            r2 = mm.load_tts_model()

        assert r1 is r2 is fake_model
        assert load_count[0] == 1, "_load_f5 called more than once — not idempotent"

    finally:
        mm._tts_model = original_tts
        mm._tts_slot_owner = original_owner


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_factory_returns_f5_adapter() -> None:
    from app.services.tts.f5_adapter import F5TTSAdapter
    from app.services.tts.factory import get_tts_engine

    with patch("app.services.tts.factory.settings") as mock_settings:
        mock_settings.tts_engine = "f5"
        engine = get_tts_engine()

    assert isinstance(engine, F5TTSAdapter)


def test_factory_returns_xtts_adapter() -> None:
    from app.services.tts.factory import get_tts_engine
    from app.services.tts.xtts_adapter import XTTSAdapter

    with patch("app.services.tts.factory.settings") as mock_settings:
        mock_settings.tts_engine = "xtts"
        engine = get_tts_engine()

    assert isinstance(engine, XTTSAdapter)


def test_factory_with_fallback_returns_f5_on_success() -> None:
    from app.services.tts.f5_adapter import F5TTSAdapter
    from app.services.tts.factory import get_tts_engine_with_fallback

    engine = get_tts_engine_with_fallback()
    assert isinstance(engine, F5TTSAdapter)


def test_factory_with_fallback_returns_xtts_when_f5_unavailable() -> None:
    """get_tts_engine_with_fallback() returns XTTSAdapter when f5_adapter import fails."""
    import sys

    from app.services.tts.factory import get_tts_engine_with_fallback
    from app.services.tts.xtts_adapter import XTTSAdapter

    # Temporarily hide the f5_adapter module so the import inside the try-block fails
    with patch.dict(sys.modules, {"app.services.tts.f5_adapter": None}):  # type: ignore[dict-item]
        engine = get_tts_engine_with_fallback()

    assert isinstance(engine, XTTSAdapter)


# ---------------------------------------------------------------------------
# Slow / integration tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW_TESTS"),
    reason="Skipped unless RUN_SLOW_TESTS=1 (requires GPU and model download)",
)
def test_f5_real_synthesis(tmp_path: Path) -> None:
    """F5-TTS produces a WAV with duration > 0 on real hardware."""
    import asyncio

    from app.services.tts.f5_adapter import F5TTSAdapter

    ref_path = tmp_path / "ref.wav"
    out_path = tmp_path / "out.wav"
    _write_wav(ref_path, duration_s=5.0)

    adapter = F5TTSAdapter()
    result = asyncio.run(
        adapter.synthesize(
            text="This is a short test sentence for the benchmark.",
            reference_audio_path=ref_path,
            output_path=out_path,
        )
    )

    assert out_path.exists()
    assert result.duration_seconds > 0.0
    assert result.engine_used == "f5"
    # On a 4 GB device used_gpu may be False if OOM fallback triggered
    assert isinstance(result.used_gpu, bool)
