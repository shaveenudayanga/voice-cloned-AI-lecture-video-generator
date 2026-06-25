# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

import pytest

from app.services.slides.mime import sniff_mime

FIXTURES = Path(__file__).parent.parent / "fixtures"

PPTX_CTYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def test_sniff_pdf_from_header() -> None:
    pdf_bytes = (FIXTURES / "sample_3page.pdf").read_bytes()
    result = sniff_mime(pdf_bytes[:8], "application/pdf")
    assert result == "application/pdf"


def test_sniff_pdf_ignores_declared_type() -> None:
    """Magic bytes win over declared content-type for PDF."""
    pdf_bytes = (FIXTURES / "sample_3page.pdf").read_bytes()
    # Even if the client claims it's a PPTX, magic bytes say PDF
    result = sniff_mime(pdf_bytes[:8], PPTX_CTYPE)
    assert result == "application/pdf"


def test_sniff_pptx_requires_correct_declared_type() -> None:
    pptx_bytes = (FIXTURES / "sample_3slide.pptx").read_bytes()
    result = sniff_mime(pptx_bytes[:8], PPTX_CTYPE)
    assert result == PPTX_CTYPE


def test_sniff_pptx_rejected_without_correct_declared_type() -> None:
    """A ZIP file claiming to be a PDF must be rejected."""
    pptx_bytes = (FIXTURES / "sample_3slide.pptx").read_bytes()
    result = sniff_mime(pptx_bytes[:8], "application/pdf")
    assert result is None


def test_sniff_unknown_returns_none() -> None:
    # Fake EXE header
    result = sniff_mime(b"MZ\x00\x00\x00\x00\x00\x00", "application/pdf")
    assert result is None


def test_factory_raises_for_unsupported_mime() -> None:
    from app.domain.exceptions import ValidationError
    from app.services.slides.factory import get_slide_parser

    with pytest.raises(ValidationError):
        get_slide_parser("application/x-executable")


def test_factory_returns_pdf_parser() -> None:
    from app.services.slides.factory import get_slide_parser
    from app.services.slides.pdf_parser import PdfSlideParser

    parser = get_slide_parser("application/pdf")
    assert isinstance(parser, PdfSlideParser)


def test_factory_returns_pptx_parser() -> None:
    from app.services.slides.factory import get_slide_parser
    from app.services.slides.pptx_parser import PptxSlideParser

    parser = get_slide_parser(PPTX_CTYPE)
    assert isinstance(parser, PptxSlideParser)
