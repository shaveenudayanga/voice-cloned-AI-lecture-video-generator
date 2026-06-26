# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class SynthesisResult:
    """Returned by every TTSEngine.synthesize* call."""

    output_path: Path
    duration_seconds: float
    engine_used: str
    used_gpu: bool


@runtime_checkable
class TTSEngine(Protocol):
    """Pluggable TTS engine. Implementations: F5-TTS (primary), XTTS-v2 (fallback).

    All methods write audio to a caller-supplied output_path and return a
    SynthesisResult.  The caller owns the temp directory lifecycle.
    Model loading is handled by model_manager, not inside the adapter.
    """

    async def synthesize(
        self,
        text: str,
        reference_audio_path: Path,
        output_path: Path,
        pronunciation_hints: str | None = None,
    ) -> SynthesisResult:
        """Synthesize full narration text in the reference voice."""
        ...

    async def synthesize_preview(
        self,
        text: str,
        reference_audio_path: Path,
        output_path: Path,
    ) -> SynthesisResult:
        """Synthesize a fixed test sentence to confirm clone quality."""
        ...
