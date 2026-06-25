# SPDX-License-Identifier: Apache-2.0
"""
F5-TTS adapter. License: CC-BY-NC-4.0 (non-commercial use only — see docs/LICENSE_AUDIT.md).
Model is loaded once at worker startup via warm_up(); never inside a task body.
"""
import asyncio
import tempfile
from pathlib import Path
from typing import Any

import structlog

from app.services.tts.interface import SynthesisResult

logger = structlog.get_logger(__name__)

_model: Any = None


def _get_model() -> Any:
    global _model
    if _model is None:
        from f5_tts.api import F5TTS  # type: ignore[import-untyped,unused-ignore]

        logger.info("f5tts_model_loading")
        _model = F5TTS()
        logger.info("f5tts_model_loaded")
    return _model


class F5TTSEngine:
    """F5-TTS voice cloning engine."""

    def warm_up(self) -> None:
        _get_model()

    async def synthesize(
        self,
        text: str,
        reference_audio: bytes,
        params: dict[str, object] | None = None,
    ) -> SynthesisResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text, reference_audio, params or {})

    def _synthesize_sync(self, text: str, reference_audio: bytes, params: dict[str, object]) -> SynthesisResult:
        import soundfile as sf  # type: ignore[import-untyped,unused-ignore]

        model = _get_model()

        with tempfile.TemporaryDirectory() as tmpdir:
            ref_path = Path(tmpdir) / "ref.wav"
            out_path = Path(tmpdir) / "out.wav"
            ref_path.write_bytes(reference_audio)

            model.infer(
                ref_file=str(ref_path),
                ref_text="",
                gen_text=text,
                file_wave=str(out_path),
                **params,
            )

            audio_data, sample_rate = sf.read(str(out_path))
            duration_s = len(audio_data) / sample_rate
            wav_bytes = out_path.read_bytes()

        logger.info("f5tts_synthesized", duration_s=duration_s)
        return SynthesisResult(audio_wav=wav_bytes, duration_s=duration_s, sample_rate=sample_rate)
