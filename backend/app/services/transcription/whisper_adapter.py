# SPDX-License-Identifier: Apache-2.0
import tempfile
from pathlib import Path
from typing import Any

import structlog

from app.domain.exceptions import TranscriptionError
from app.services.transcription.interface import TranscriptionResult

logger = structlog.get_logger(__name__)


def _get_model() -> Any:
    """Return the Whisper model, loading it via model_manager (warm worker, §7.3).

    model_manager handles VRAM eviction of TTS if VRAM_BUDGET_GB < 6.0,
    ensuring F5-TTS and Whisper never coexist on low-VRAM devices.
    """
    from app.services.tts.model_manager import load_whisper_model

    return load_whisper_model()


class WhisperTranscriber:
    """faster-whisper adapter. Model is loaded once per worker via model_manager."""

    async def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_bytes)

    def _transcribe_sync(self, audio_bytes: bytes) -> TranscriptionResult:
        try:
            model = _get_model()

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            try:
                segments, info = model.transcribe(tmp_path, beam_size=5)
                text = " ".join(seg.text.strip() for seg in segments)
                logger.info(
                    "whisper_transcribed",
                    language=info.language,
                    duration=info.duration,
                )
                return TranscriptionResult(
                    text=text,
                    language=info.language,
                    duration_s=info.duration,
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except Exception as exc:
            raise TranscriptionError(f"Whisper transcription failed: {exc}") from exc
