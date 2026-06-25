# SPDX-License-Identifier: Apache-2.0
"""
XTTS-v2 adapter via coqui-tts (idiap fork). License: CPML (non-commercial).
PyTorch >=2.6 requires torch.serialization.add_safe_globals workaround — encapsulated here.
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
        import torch
        from TTS.api import TTS  # type: ignore[import-untyped,unused-ignore]
        from TTS.tts.configs.xtts_config import XttsConfig  # type: ignore[import-untyped,unused-ignore]
        from TTS.tts.models.xtts import XttsAudioConfig  # type: ignore[import-untyped,unused-ignore]

        # Workaround: PyTorch >=2.6 restricts deserialization of arbitrary classes.
        # XTTS-v2 weight files embed these config classes — we must allowlist them.
        torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig])

        logger.info("xtts_model_loading")
        _model = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2").to(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        logger.info("xtts_model_loaded")
    return _model


class XTTSEngine:
    """XTTS-v2 fallback TTS engine."""

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

            model.tts_to_file(
                text=text,
                speaker_wav=str(ref_path),
                language=params.get("language", "en"),
                file_path=str(out_path),
            )

            audio_data, sample_rate = sf.read(str(out_path))
            duration_s = len(audio_data) / sample_rate
            wav_bytes = out_path.read_bytes()

        logger.info("xtts_synthesized", duration_s=duration_s)
        return SynthesisResult(audio_wav=wav_bytes, duration_s=duration_s, sample_rate=sample_rate)
