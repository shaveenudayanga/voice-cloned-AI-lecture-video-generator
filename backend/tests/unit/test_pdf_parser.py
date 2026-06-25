# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.mark.asyncio
async def test_pdf_parser_returns_three_slides() -> None:
    from app.services.slides.pdf_parser import PdfSlideParser

    pdf_bytes = (FIXTURES / "sample_3page.pdf").read_bytes()
    parser = PdfSlideParser()
    slides = await parser.parse(pdf_bytes)

    assert len(slides) == 3


@pytest.mark.asyncio
async def test_pdf_parser_slide_fields() -> None:
    from app.services.slides.pdf_parser import PdfSlideParser

    pdf_bytes = (FIXTURES / "sample_3page.pdf").read_bytes()
    parser = PdfSlideParser()
    slides = await parser.parse(pdf_bytes)

    for i, slide in enumerate(slides):
        assert slide.order_index == i
        assert len(slide.image_png) > 0, f"Slide {i} has empty image_png"
        assert slide.image_png[:4] == b"\x89PNG", f"Slide {i} image is not a PNG"
        assert len(slide.extracted_text) > 0, f"Slide {i} has empty extracted_text"


@pytest.mark.asyncio
async def test_pdf_parser_text_content() -> None:
    from app.services.slides.pdf_parser import PdfSlideParser

    pdf_bytes = (FIXTURES / "sample_3page.pdf").read_bytes()
    parser = PdfSlideParser()
    slides = await parser.parse(pdf_bytes)

    assert "Machine Learning" in slides[0].extracted_text
