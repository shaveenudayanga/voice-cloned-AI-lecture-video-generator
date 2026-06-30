# SPDX-License-Identifier: Apache-2.0
"""
PPTX parser unit tests.

LibreOffice is not available in the unit-test environment, so we mock the
subprocess step and verify the parser correctly delegates to PdfSlideParser
after the conversion succeeds.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"
PDF_BYTES = (FIXTURES / "sample_3page.pdf").read_bytes()


@pytest.mark.asyncio
async def test_pptx_parser_delegates_to_pdf_parser() -> None:
    """After LibreOffice converts PPTX → PDF, output should be 3 slides."""
    from app.services.slides.pptx_parser import PptxSlideParser

    pptx_bytes = (FIXTURES / "sample_3slide.pptx").read_bytes()

    # Mock the LibreOffice subprocess so the test does not need soffice installed
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=PDF_BYTES),
    ):
        parser = PptxSlideParser()
        slides = await parser.parse(pptx_bytes)

    # LibreOffice was invoked
    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert call_args[0] == "soffice"
    assert "--headless" in call_args
    assert "--convert-to" in call_args
    assert "pdf" in call_args

    # Resulting slides come from the PDF parser applied to the converted bytes
    assert len(slides) == 3
    for i, slide in enumerate(slides):
        assert slide.order_index == i
        assert len(slide.image_png) > 0
        assert slide.image_png[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_pptx_parser_raises_on_libreoffice_failure() -> None:
    from app.services.slides.pptx_parser import PptxSlideParser

    pptx_bytes = (FIXTURES / "sample_3slide.pptx").read_bytes()

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"conversion error"))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        parser = PptxSlideParser()
        with pytest.raises(RuntimeError, match="LibreOffice conversion failed"):
            await parser.parse(pptx_bytes)
