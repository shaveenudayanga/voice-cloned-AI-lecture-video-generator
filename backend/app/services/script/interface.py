# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class GeneratedScript:
    text: str
    estimated_reading_seconds: int
    pronunciation_hints: str | None


@runtime_checkable
class LLMScriptGenerator(Protocol):
    """Generates per-slide narration scripts from slide image + text + style reference."""

    async def generate(
        self,
        slide_image_bytes: bytes,
        slide_text: str,
        style_reference: str | None,
        pronunciation_hints: str | None,
    ) -> GeneratedScript:
        """Return a script that explains the slide in the professor's own vocabulary and style."""
        ...
