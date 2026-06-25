# SPDX-License-Identifier: Apache-2.0
import tempfile
from pathlib import Path
from typing import Any

import structlog

from app.core.config import settings
from app.services.transcription.interface import TranscriptionResult

logger = structlog.get_logger(__name__)

# Module-level singleton — loaded once per worker process (§7.3 warm worker)
_model: Any = None


def _get_model() -> Any:
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        logger.info("whisper_model_loading", size=settings.whisper_model_size)
        _model = WhisperModel(
            settings.whisper_model_size,
            device="auto",
            compute_type="float16",
        )
        logger.info("whisper_model_loaded", size=settings.whisper_model_size)
    return _model


class WhisperTranscriber:
    """faster-whisper adapter. Model is loaded once at worker startup."""

    async def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_bytes)

    def _transcribe_sync(self, audio_bytes: bytes) -> TranscriptionResult:
        model = _get_model()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            segments, info = model.transcribe(tmp_path, beam_size=5)
            text = " ".join(seg.text.strip() for seg in segments)
            logger.info("whisper_transcribed", language=info.language, duration=info.duration)
            return TranscriptionResult(
                text=text,
                language=info.language,
                duration_s=info.duration,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
