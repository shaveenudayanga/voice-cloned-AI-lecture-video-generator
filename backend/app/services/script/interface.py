# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class GeneratedScript:
    narration_text: str
    estimated_reading_time_s: float
    pronunciation_hints: str | None


@runtime_checkable
class LLMScriptGenerator(Protocol):
    """Generates per-slide narration scripts from slide image + text + style reference."""

    async def generate(
        self,
        slide_image_png: bytes,
        slide_text: str,
        style_reference_transcript: str,
        extra_style_sample: str | None = None,
    ) -> GeneratedScript:
        """Return a script that explains the slide in the professor's own vocabulary."""
        ...
