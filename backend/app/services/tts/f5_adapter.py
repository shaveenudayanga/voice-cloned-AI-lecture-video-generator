# SPDX-License-Identifier: Apache-2.0
"""
F5-TTS adapter. License: CC-BY-NC-4.0 (non-commercial only — see docs/LICENSE_AUDIT.md).

Model is loaded via model_manager once at worker startup; never inside a task body.
FP16 is enforced in model_manager._load_f5() for 4 GB VRAM devices.
"""
import asyncio
import wave
from pathlib import Path
from typing import Any

import structlog

from app.services.tts.interface import SynthesisResult

logger = structlog.get_logger(__name__)

_PREVIEW_TEXT = (
    "Hello, this is a preview of my cloned voice for lecture recordings. "
    "How does this sound?"
)

_ENGINE_NAME = "f5"


class F5TTSAdapter:
    """F5-TTS voice cloning engine. Delegates model management to model_manager."""

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
        from app.services.tts.model_manager import get_vram_free_gb, load_tts_model

        model = load_tts_model()
        used_gpu = _is_cuda(model)

        try:
            _run_f5_infer(model, text, reference_audio_path, output_path)
        except Exception as exc:
            if _is_oom(exc):
                free_gb = get_vram_free_gb()
                logger.warning(
                    "f5tts_cuda_oom_cpu_fallback",
                    free_vram_gb=free_gb,
                    error=str(exc),
                )
                # CPU fallback: temporary model instance, not cached through model_manager
                import torch
                from f5_tts.api import F5TTS
                cpu_model = F5TTS(device="cpu", dtype=torch.float32)
                _run_f5_infer(cpu_model, text, reference_audio_path, output_path)
                used_gpu = False
            else:
                raise

        duration = _wav_duration(output_path)
        logger.info("f5tts_synthesized", duration_s=duration, used_gpu=used_gpu)
        return SynthesisResult(
            output_path=output_path,
            duration_seconds=duration,
            engine_used=_ENGINE_NAME,
            used_gpu=used_gpu,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_f5_infer(model: Any, text: str, ref_path: Path, out_path: Path) -> None:
    model.infer(
        ref_file=str(ref_path),
        ref_text="",
        gen_text=text,
        file_wave=str(out_path),
    )


def _is_oom(exc: Exception) -> bool:
    try:
        import torch
        return isinstance(exc, torch.cuda.OutOfMemoryError)
    except Exception:
        return False


def _is_cuda(model: Any) -> bool:
    """Return True if the model appears to be on a CUDA device."""
    try:
        import torch
        # F5TTS stores its internal model; check the first parameter device
        params = list(model.ema_model.parameters())
        return bool(params and params[0].device.type == "cuda")
    except Exception:
        try:
            return bool(torch.cuda.is_available())
        except Exception:
            return False


def _wav_duration(path: Path) -> float:
    with wave.open(str(path)) as wf:
        return float(wf.getnframes()) / float(wf.getframerate())
