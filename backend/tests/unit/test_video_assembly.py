# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for Phase 6 — video assembly:
  - SRT generator (content, cumulative timing, precision)
  - VideoAssembler subprocess calls (list args, hwaccel flag, failure handling)
  - probe.get_audio_duration (wave fallback)
  - POST /api/v1/projects/{id}/video/assemble endpoint (202 + 422 + 404)
  - GET /api/v1/projects/{id}/video/ endpoint (404 + 200)
"""
import io
import os
import subprocess
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


def _make_png_bytes() -> bytes:
    """Minimal valid 1x1 PNG."""
    import base64
    # 1x1 white PNG, base64-encoded
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
    )


def _make_pair(
    order_index: int,
    duration_s: float,
    script_text: str,
    tmp_path: Path,
) -> "Any":
    from app.services.video.assembler import SlideAudioPair

    img = tmp_path / f"slide_{order_index}.png"
    aud = tmp_path / f"audio_{order_index}.wav"
    img.write_bytes(_make_png_bytes())
    aud.write_bytes(_make_wav_bytes(duration_s))
    return SlideAudioPair(
        order_index=order_index,
        image_path=img,
        audio_path=aud,
        script_text=script_text,
        duration_seconds=duration_s,
    )


# ---------------------------------------------------------------------------
# SRT generator — content
# ---------------------------------------------------------------------------


def test_srt_generator_three_slides_entry_count(tmp_path: Path) -> None:
    """Three SlideAudioPairs → exactly three SRT entries."""
    from app.services.video.srt_generator import generate_srt

    pairs = [
        _make_pair(0, 10.0, "Slide one text.", tmp_path),
        _make_pair(1, 15.5, "Slide two text.", tmp_path),
        _make_pair(2, 8.3, "Slide three text.", tmp_path),
    ]
    srt = generate_srt(pairs)
    # Count sequence numbers by splitting on blank lines
    entries = [e for e in srt.strip().split("\n\n") if e.strip()]
    assert len(entries) == 3


def test_srt_generator_text_matches_script(tmp_path: Path) -> None:
    """Each SRT entry body must match the pair's script_text."""
    from app.services.video.srt_generator import generate_srt

    texts = ["First slide narration.", "Second slide narration.", "Third slide."]
    pairs = [
        _make_pair(0, 10.0, texts[0], tmp_path),
        _make_pair(1, 15.5, texts[1], tmp_path),
        _make_pair(2, 8.3, texts[2], tmp_path),
    ]
    srt = generate_srt(pairs)
    for text in texts:
        assert text in srt


def test_srt_generator_cumulative_timing(tmp_path: Path) -> None:
    """Timings must be cumulative: entry 2 starts where entry 1 ended, etc."""
    from app.services.video.srt_generator import generate_srt

    pairs = [
        _make_pair(0, 10.0, "A", tmp_path),
        _make_pair(1, 15.5, "B", tmp_path),
        _make_pair(2, 8.3, "C", tmp_path),
    ]
    srt = generate_srt(pairs)
    # Entry 1: 00:00:00,000 --> 00:00:10,000
    assert "00:00:00,000 --> 00:00:10,000" in srt
    # Entry 2: 00:00:10,000 --> 00:00:25,500
    assert "00:00:10,000 --> 00:00:25,500" in srt
    # Entry 3: 00:00:25,500 --> 00:00:33,800
    assert "00:00:25,500 --> 00:00:33,800" in srt


def test_srt_generator_timing_precision(tmp_path: Path) -> None:
    """Cumulative offset must be within ±10 ms of expected values."""
    from app.services.video.srt_generator import _fmt_srt_time, generate_srt

    durations = [10.0, 15.5, 8.3]
    pairs = [_make_pair(i, d, f"text {i}", tmp_path) for i, d in enumerate(durations)]
    srt = generate_srt(pairs)
    lines = srt.splitlines()

    # Collect --> lines
    timing_lines = [ln for ln in lines if "-->" in ln]
    assert len(timing_lines) == 3

    cumulative = 0.0
    for i, (dur, tline) in enumerate(zip(durations, timing_lines, strict=True)):
        expected_start = _fmt_srt_time(cumulative)
        expected_end = _fmt_srt_time(cumulative + dur)
        assert tline.startswith(expected_start), f"entry {i}: start mismatch"
        assert tline.endswith(expected_end), f"entry {i}: end mismatch"
        cumulative += dur


def test_srt_generator_ordering_by_order_index(tmp_path: Path) -> None:
    """Pairs passed in reverse order must be sorted by order_index before generating SRT."""
    from app.services.video.srt_generator import generate_srt

    # Pass in reverse order
    pairs = [
        _make_pair(2, 5.0, "Last", tmp_path),
        _make_pair(0, 3.0, "First", tmp_path),
        _make_pair(1, 4.0, "Middle", tmp_path),
    ]
    srt = generate_srt(pairs)
    lines = srt.splitlines()

    # First sequence number entry body should be "First"
    assert "First" in lines[2]
    # Verify first timestamp starts at 00:00:00,000
    assert lines[1].startswith("00:00:00,000")


# ---------------------------------------------------------------------------
# VideoAssembler — subprocess args (mocked)
# ---------------------------------------------------------------------------


def test_assembler_uses_list_args_not_shell(tmp_path: Path) -> None:
    """ffmpeg must always be called with list args; shell=True must never appear."""
    from app.services.video.assembler import SlideAudioPair, VideoAssembler

    pair = SlideAudioPair(
        order_index=0,
        image_path=tmp_path / "slide.png",
        audio_path=tmp_path / "audio.wav",
        script_text="Test",
        duration_seconds=3.0,
    )
    (tmp_path / "slide.png").write_bytes(_make_png_bytes())
    (tmp_path / "audio.wav").write_bytes(_make_wav_bytes(3.0))
    output = tmp_path / "out.mp4"
    srt_out = tmp_path / "out.srt"

    recorded_calls: list[dict[str, Any]] = []

    def fake_run(cmd: list[str], timeout: int = 300, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        recorded_calls.append({"cmd": cmd, "kwargs": kwargs})
        # Create a dummy output file on the concat call
        if "-f" in cmd and "concat" in cmd:
            output.write_bytes(b"fakevideo")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    assembler = VideoAssembler(use_hwaccel=False)
    with (
        patch("app.services.video.assembler._run_ffmpeg", side_effect=fake_run),
        patch("app.services.video.assembler._get_ffmpeg_version", return_value="ffmpeg version test"),
    ):
        import asyncio

        asyncio.run(assembler.assemble([pair], output, srt_out))

    for recorded in recorded_calls:
        cmd = recorded["cmd"]
        assert isinstance(cmd, list), "ffmpeg must be called with list args"
        # Verify no shell=True was passed
        assert recorded["kwargs"].get("shell") is not True


def test_assembler_no_hwaccel_when_disabled(tmp_path: Path) -> None:
    """When use_hwaccel=False, -hwaccel auto must NOT appear in the segment command."""
    from app.services.video.assembler import SlideAudioPair, VideoAssembler

    pair = SlideAudioPair(
        order_index=0,
        image_path=tmp_path / "slide.png",
        audio_path=tmp_path / "audio.wav",
        script_text="Test",
        duration_seconds=2.0,
    )
    (tmp_path / "slide.png").write_bytes(_make_png_bytes())
    (tmp_path / "audio.wav").write_bytes(_make_wav_bytes(2.0))
    output = tmp_path / "out.mp4"
    srt_out = tmp_path / "out.srt"

    segment_cmds: list[list[str]] = []

    def fake_run(cmd: list[str], timeout: int = 300, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        if "-loop" in cmd:  # segment encode cmd
            segment_cmds.append(cmd)
        if "-f" in cmd and "concat" in cmd:
            output.write_bytes(b"fakevideo")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    assembler = VideoAssembler(use_hwaccel=False)
    with (
        patch("app.services.video.assembler._run_ffmpeg", side_effect=fake_run),
        patch("app.services.video.assembler._get_ffmpeg_version", return_value="v0"),
    ):
        import asyncio

        asyncio.run(assembler.assemble([pair], output, srt_out))

    assert segment_cmds, "No segment ffmpeg command was recorded"
    for cmd in segment_cmds:
        assert "-hwaccel" not in cmd, "-hwaccel must be absent when use_hwaccel=False"
        assert "auto" not in cmd


def test_assembler_hwaccel_present_when_enabled(tmp_path: Path) -> None:
    """When use_hwaccel=True, -hwaccel auto must appear in the segment command."""
    from app.services.video.assembler import SlideAudioPair, VideoAssembler

    pair = SlideAudioPair(
        order_index=0,
        image_path=tmp_path / "slide.png",
        audio_path=tmp_path / "audio.wav",
        script_text="Test",
        duration_seconds=2.0,
    )
    (tmp_path / "slide.png").write_bytes(_make_png_bytes())
    (tmp_path / "audio.wav").write_bytes(_make_wav_bytes(2.0))
    output = tmp_path / "out.mp4"
    srt_out = tmp_path / "out.srt"

    segment_cmds: list[list[str]] = []

    def fake_run(cmd: list[str], timeout: int = 300, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        if "-loop" in cmd:
            segment_cmds.append(cmd)
        if "-f" in cmd and "concat" in cmd:
            output.write_bytes(b"fakevideo")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    assembler = VideoAssembler(use_hwaccel=True)
    with (
        patch("app.services.video.assembler._run_ffmpeg", side_effect=fake_run),
        patch("app.services.video.assembler._get_ffmpeg_version", return_value="v0"),
    ):
        import asyncio

        asyncio.run(assembler.assemble([pair], output, srt_out))

    assert segment_cmds, "No segment ffmpeg command recorded"
    assert "-hwaccel" in segment_cmds[0]
    assert "auto" in segment_cmds[0]


def test_assembler_raises_on_ffmpeg_failure(tmp_path: Path) -> None:
    """Non-zero ffmpeg exit code must raise VideoAssemblyError containing stderr."""
    from app.domain.exceptions import VideoAssemblyError
    from app.services.video.assembler import SlideAudioPair, VideoAssembler

    pair = SlideAudioPair(
        order_index=0,
        image_path=tmp_path / "slide.png",
        audio_path=tmp_path / "audio.wav",
        script_text="Test",
        duration_seconds=2.0,
    )
    (tmp_path / "slide.png").write_bytes(_make_png_bytes())
    (tmp_path / "audio.wav").write_bytes(_make_wav_bytes(2.0))
    output = tmp_path / "out.mp4"
    srt_out = tmp_path / "out.srt"

    stderr_msg = b"Codec not found: somebadcodec\n"

    def fake_run(cmd: list[str], timeout: int = 300, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(cmd, 1, b"", stderr_msg)

    assembler = VideoAssembler(use_hwaccel=False)
    with (
        patch("app.services.video.assembler._run_ffmpeg", side_effect=fake_run),
        patch("app.services.video.assembler._get_ffmpeg_version", return_value="v0"),
    ):
        import asyncio

        with pytest.raises(VideoAssemblyError) as exc_info:
            asyncio.run(assembler.assemble([pair], output, srt_out))

    assert "somebadcodec" in str(exc_info.value)


# ---------------------------------------------------------------------------
# probe.get_audio_duration — wave fallback
# ---------------------------------------------------------------------------


def test_probe_get_audio_duration_wave_fallback(tmp_path: Path) -> None:
    """When ffprobe is absent/failing, fall back to wave module for duration."""
    from app.services.video.probe import get_audio_duration

    duration_s = 3.7
    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(_make_wav_bytes(duration_s))

    # Simulate ffprobe not found
    with patch("app.services.video.probe.subprocess.run", side_effect=FileNotFoundError):
        measured = get_audio_duration(wav_path)

    assert abs(measured - duration_s) < 0.02


def test_probe_get_audio_duration_uses_ffprobe_first(tmp_path: Path) -> None:
    """When ffprobe succeeds, its result is returned directly."""
    import json

    from app.services.video.probe import get_audio_duration

    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(_make_wav_bytes(1.0))

    fake_output = json.dumps({"format": {"duration": "12.345"}}).encode()

    with patch(
        "app.services.video.probe.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, fake_output, b""),
    ):
        measured = get_audio_duration(wav_path)

    assert abs(measured - 12.345) < 0.001


# ---------------------------------------------------------------------------
# API endpoint — POST /api/v1/projects/{id}/video/assemble
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_video_assemble_endpoint_202(client: Any) -> None:
    """POST /api/v1/projects/{id}/video/assemble → 202 when all clips exist."""
    import datetime

    from app.db.session import get_session
    from app.main import app

    project_id = uuid.uuid4()
    slide_id = uuid.uuid4()
    job_id = uuid.uuid4()

    now = datetime.datetime.now(datetime.UTC)

    from app.domain.entities import AudioClip, Job, Project, Slide
    from app.domain.value_objects import BlobKey

    mock_project = Project(
        id=project_id,
        user_id=uuid.uuid5(uuid.NAMESPACE_OID, "test-api-key"),
        title="Test",
        voice_profile_id=uuid.uuid4(),
        wizard_step="audio",
        created_at=now,
        updated_at=now,
    )
    mock_slide = Slide(
        id=slide_id,
        project_id=project_id,
        order_index=0,
        image_blob=BlobKey(bucket="b", key="k"),
        extracted_text="text",
        created_at=now,
    )
    mock_clip = AudioClip(
        id=uuid.uuid4(),
        project_id=project_id,
        slide_id=slide_id,
        script_id=uuid.uuid4(),
        voice_profile_id=uuid.uuid4(),
        audio_blob=BlobKey(bucket="b", key="a.wav"),
        duration_seconds=5.0,
        engine_used="f5",
        synthesis_fingerprint="fp",
        created_at=now,
    )
    mock_job = Job(
        id=job_id,
        task_name="video_assembly",
        status="pending",
        progress_pct=0,
        result_payload=None,
        error_message=None,
        created_at=now,
        updated_at=now,
        related_entity_id=project_id,
    )

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    from app.db.repositories.audio_clip_repository import AudioClipRepository
    from app.db.repositories.job_repository import JobRepository
    from app.db.repositories.project_repository import ProjectRepository
    from app.db.repositories.slide_repository import SlideRepository

    async def override_session() -> Any:
        yield mock_session

    app.dependency_overrides[get_session] = override_session

    with (
        patch.object(ProjectRepository, "get", AsyncMock(return_value=mock_project)),
        patch.object(SlideRepository, "list_by_project", AsyncMock(return_value=[mock_slide])),
        patch.object(AudioClipRepository, "list_by_project", AsyncMock(return_value=[mock_clip])),
        patch.object(JobRepository, "create", AsyncMock(return_value=mock_job)),
        patch("app.api.v1.video.assemble_video") as mock_task,
    ):
        mock_task.delay = MagicMock()
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"/api/v1/projects/{project_id}/video/assemble",
                headers={"X-API-Key": "test-api-key"},
            )

    app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["project_id"] == str(project_id)
    assert "job_id" in body
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_video_assemble_endpoint_422_missing_clips(client: Any) -> None:
    """POST assemble → 422 when AudioClips are missing for some slides."""
    import datetime

    from app.db.session import get_session
    from app.main import app

    project_id = uuid.uuid4()
    slide_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.UTC)

    from app.domain.entities import Project, Slide
    from app.domain.value_objects import BlobKey

    mock_project = Project(
        id=project_id,
        user_id=uuid.uuid5(uuid.NAMESPACE_OID, "test-api-key"),
        title="Test",
        voice_profile_id=uuid.uuid4(),
        wizard_step="audio",
        created_at=now,
        updated_at=now,
    )
    mock_slide = Slide(
        id=slide_id,
        project_id=project_id,
        order_index=0,
        image_blob=BlobKey(bucket="b", key="k"),
        extracted_text="text",
        created_at=now,
    )

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    from app.db.repositories.audio_clip_repository import AudioClipRepository
    from app.db.repositories.project_repository import ProjectRepository
    from app.db.repositories.slide_repository import SlideRepository

    async def override_session() -> Any:
        yield mock_session

    app.dependency_overrides[get_session] = override_session

    with (
        patch.object(ProjectRepository, "get", AsyncMock(return_value=mock_project)),
        patch.object(SlideRepository, "list_by_project", AsyncMock(return_value=[mock_slide])),
        patch.object(AudioClipRepository, "list_by_project", AsyncMock(return_value=[])),
    ):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"/api/v1/projects/{project_id}/video/assemble",
                headers={"X-API-Key": "test-api-key"},
            )

    app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 422
    assert "missing audio clips" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# API endpoint — GET /api/v1/projects/{id}/video/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_video_artifact_404_before_assembly(client: Any) -> None:
    """GET /projects/{id}/video/ → 404 when no artifact exists."""
    import datetime

    from app.db.session import get_session
    from app.main import app

    project_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.UTC)

    from app.domain.entities import Project

    mock_project = Project(
        id=project_id,
        user_id=uuid.uuid5(uuid.NAMESPACE_OID, "test-api-key"),
        title="Test",
        voice_profile_id=None,
        wizard_step="scripts",
        created_at=now,
        updated_at=now,
    )

    mock_session = AsyncMock()

    from app.db.repositories.project_repository import ProjectRepository
    from app.db.repositories.video_artifact_repository import VideoArtifactRepository

    async def override_session() -> Any:
        yield mock_session

    app.dependency_overrides[get_session] = override_session

    with (
        patch.object(ProjectRepository, "get", AsyncMock(return_value=mock_project)),
        patch.object(VideoArtifactRepository, "get_by_project", AsyncMock(return_value=None)),
    ):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(
                f"/api/v1/projects/{project_id}/video/",
                headers={"X-API-Key": "test-api-key"},
            )

    app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_video_artifact_200_after_assembly(client: Any) -> None:
    """GET /projects/{id}/video/ → 200 with artifact data after assembly."""
    import datetime

    from app.db.session import get_session
    from app.main import app

    project_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.UTC)

    from app.domain.entities import Project, VideoArtifact
    from app.domain.value_objects import BlobKey

    mock_project = Project(
        id=project_id,
        user_id=uuid.uuid5(uuid.NAMESPACE_OID, "test-api-key"),
        title="Test",
        voice_profile_id=None,
        wizard_step="done",
        created_at=now,
        updated_at=now,
    )
    mock_artifact = VideoArtifact(
        id=artifact_id,
        project_id=project_id,
        video_blob=BlobKey(bucket="lv", key="projects/test/output/lecture.mp4"),
        srt_blob=BlobKey(bucket="lv", key="projects/test/output/lecture.srt"),
        total_duration_seconds=33.8,
        slide_count=3,
        ffmpeg_version="ffmpeg version 7.0",
        created_at=now,
    )

    mock_session = AsyncMock()

    from app.db.repositories.project_repository import ProjectRepository
    from app.db.repositories.video_artifact_repository import VideoArtifactRepository

    async def override_session() -> Any:
        yield mock_session

    app.dependency_overrides[get_session] = override_session

    with (
        patch.object(ProjectRepository, "get", AsyncMock(return_value=mock_project)),
        patch.object(VideoArtifactRepository, "get_by_project", AsyncMock(return_value=mock_artifact)),
    ):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(
                f"/api/v1/projects/{project_id}/video/",
                headers={"X-API-Key": "test-api-key"},
            )

    app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["slide_count"] == 3
    assert abs(body["total_duration_seconds"] - 33.8) < 0.01
    assert "lecture.mp4" in body["video_blob_key"]
    assert "lecture.srt" in body["srt_blob_key"]


# ---------------------------------------------------------------------------
# Slow / integration — real ffmpeg required
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW_TESTS"),
    reason="Skipped unless RUN_SLOW_TESTS=1 (requires ffmpeg installed)",
)
def test_assembler_produces_mp4_with_correct_duration(tmp_path: Path) -> None:
    """Integration: given real PNG + WAV fixtures, assembler produces an MP4."""
    import asyncio

    from app.services.video.assembler import VideoAssembler
    from app.services.video.probe import get_audio_duration

    durations = [3.0, 4.0, 2.0]
    pairs = [_make_pair(i, d, f"Script {i}", tmp_path) for i, d in enumerate(durations)]

    output = tmp_path / "out.mp4"
    srt_out = tmp_path / "out.srt"

    assembler = VideoAssembler(use_hwaccel=False)
    result = asyncio.run(assembler.assemble(pairs, output, srt_out))

    assert output.exists()
    assert output.stat().st_size > 0
    assert srt_out.exists()

    video_duration = get_audio_duration(output)
    expected = sum(durations)
    assert abs(video_duration - expected) <= 1.0, (
        f"Video duration {video_duration:.2f}s differs from expected {expected:.2f}s by more than 1s"
    )
    assert result.total_duration_seconds == expected
