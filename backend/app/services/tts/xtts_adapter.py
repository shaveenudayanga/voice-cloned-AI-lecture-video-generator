# SPDX-License-Identifier: Apache-2.0
"""
XTTS-v2 fallback adapter via coqui-tts (idiap fork). License: CPML (non-commercial).

Model loading is delegated to model_manager which applies the
torch.serialization.add_safe_globals workaround required for PyTorch >= 2.6.
"""

import asyncio
import wave
from pathlib import Path
from typing import Any

import structlog

from app.services.tts.interface import SynthesisResult

logger = structlog.get_logger(__name__)

_PREVIEW_TEXT = "Hello, this is a preview of my cloned voice for lecture recordings. How does this sound?"

_ENGINE_NAME = "xtts"


class XTTSAdapter:
    """XTTS-v2 fallback TTS engine. Delegates model management to model_manager."""

    async def synthesize(
        self,
        text: str,
        reference_audio_path: Path,
        output_path: Path,
        pronunciation_hints: str | None = None,
    ) -> SynthesisResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._synthesize_sync,
            text,
            reference_audio_path,
            output_path,
        )

    async def synthesize_preview(
        self,
        text: str,
        reference_audio_path: Path,
        output_path: Path,
    ) -> SynthesisResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._synthesize_sync,
            _PREVIEW_TEXT,
            reference_audio_path,
            output_path,
        )

    def _synthesize_sync(
        self,
        text: str,
        reference_audio_path: Path,
        output_path: Path,
    ) -> SynthesisResult:
        from app.services.tts.model_manager import load_tts_model

        model = load_tts_model()
        used_gpu = _is_cuda(model)

        model.tts_to_file(
            text=text,
            speaker_wav=str(reference_audio_path),
            language="en",
            file_path=str(output_path),
        )

        duration = _wav_duration(output_path)
        logger.info("xtts_synthesized", duration_s=duration, used_gpu=used_gpu)
        return SynthesisResult(
            output_path=output_path,
            duration_seconds=duration,
            engine_used=_ENGINE_NAME,
            used_gpu=used_gpu,
        )


def _is_cuda(model: Any) -> bool:
    """Return True if the XTTS model is on a CUDA device."""
    try:
        # TTS objects expose .device
        return str(getattr(model, "device", "cpu")) == "cuda"
    except Exception:
        return False


def _wav_duration(path: Path) -> float:
    with wave.open(str(path)) as wf:
        return float(wf.getnframes()) / float(wf.getframerate())
