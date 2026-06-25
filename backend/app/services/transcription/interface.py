# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration_s: float


@runtime_checkable
class Transcriber(Protocol):
    """Transcribes voice recordings to text for LLM style-reference injection (ADR-0010)."""

    async def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        """Return the full transcript of the given audio clip."""
        ...
