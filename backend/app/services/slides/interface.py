# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ParsedSlide:
    order_index: int
    image_png: bytes
    extracted_text: str


@runtime_checkable
class SlideParser(Protocol):
    """Parses a slide deck (PDF or PPTX) into per-page images and text."""

    async def parse(self, source_bytes: bytes) -> list[ParsedSlide]:
        """Return one ParsedSlide per page, in order."""
        ...
