# SPDX-License-Identifier: Apache-2.0
"""
Tests for the voice_ingestion Celery task and WhisperTranscriber.

The @pytest.mark.slow test runs the real faster-whisper model.
It is skipped unless RUN_SLOW_TESTS=1 is set in the environment.
"""

import io
import os
import uuid
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# WAV fixture (conftest re-export so it can also be used here independently)
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


@pytest.fixture
def wav_bytes() -> bytes:
    return _make_wav_bytes(3.0)


# ---------------------------------------------------------------------------
# Unit test: voice_ingestion task with a mocked transcriber
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_voice_ingestion_task_updates_transcript() -> None:
    """voice_ingestion task persists the transcript from a mocked transcriber."""
    from app.services.transcription.interface import TranscriptionResult
    from app.tasks.voice_ingestion import _run

    profile_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    blob_key = f"users/x/voices/{profile_id}.wav"

    mock_result = TranscriptionResult(
        text="Welcome to the lecture on machine learning.",
        language="en",
        duration_s=3.0,
    )

    mock_transcriber = AsyncMock()
    mock_transcriber.transcribe = AsyncMock(return_value=mock_result)

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.close = AsyncMock()

    mock_job_repo = AsyncMock()
    mock_job_repo.update_status = AsyncMock()

    mock_voice_repo = AsyncMock()
    mock_voice_repo.update_transcript = AsyncMock()

    dummy_audio = _make_wav_bytes(1.0)
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=dummy_audio)

    # Patch at source modules since voice_ingestion._run uses local imports
    with (
        patch("app.db.session.get_task_session", new=AsyncMock(return_value=mock_session)),
        patch(
            "app.db.repositories.job_repository.JobRepository",
            new=MagicMock(return_value=mock_job_repo),
        ),
        patch(
            "app.db.repositories.voice_profile_repository.VoiceProfileRepository",
            new=MagicMock(return_value=mock_voice_repo),
        ),
        patch("app.services.storage.factory.get_blob_store", return_value=mock_store),
        patch("app.services.transcription.factory.get_transcriber", return_value=mock_transcriber),
    ):
        result = await _run(
            voice_profile_id=profile_id,
            blob_key=blob_key,
            job_id=job_id,
        )

    assert result["status"] == "ok"
    assert result["voice_profile_id"] == profile_id

    # Transcript must have been persisted to the VoiceProfile
    mock_voice_repo.update_transcript.assert_awaited_once_with(
        uuid.UUID(profile_id),
        "Welcome to the lecture on machine learning.",
    )
    # Job status must have been set to success
    success_calls = [c for c in mock_job_repo.update_status.await_args_list if c.args[1] == "success"]
    assert len(success_calls) == 1


# ---------------------------------------------------------------------------
# Slow integration test: real faster-whisper model
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW_TESTS"),
    reason="Skipped unless RUN_SLOW_TESTS=1 (downloads model on first run)",
)
def test_whisper_transcriber_on_real_wav(wav_bytes: bytes) -> None:
    """WhisperTranscriber returns a non-empty TranscriptionResult on a real WAV."""
    import asyncio

    from app.services.transcription.whisper_adapter import WhisperTranscriber

    transcriber = WhisperTranscriber()
    result = asyncio.run(transcriber.transcribe(wav_bytes))

    assert isinstance(result.text, str)
    assert isinstance(result.language, str)
    assert len(result.language) > 0
    assert result.duration_s > 0.0
