# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class SynthesisResult:
    audio_wav: bytes
    duration_s: float
    sample_rate: int


@runtime_checkable
class TTSEngine(Protocol):
    """Pluggable TTS engine interface. Implementations: F5-TTS, XTTS-v2."""

    async def synthesize(
        self,
        text: str,
        reference_audio: bytes,
        params: dict[str, object] | None = None,
    ) -> SynthesisResult:
        """Synthesize `text` in the voice of `reference_audio`."""
        ...

    def warm_up(self) -> None:
        """Load model weights into GPU VRAM. Called once at worker startup (§7.3)."""
        ...
