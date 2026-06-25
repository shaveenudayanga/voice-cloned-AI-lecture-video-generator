# SPDX-License-Identifier: Apache-2.0
from app.domain.exceptions import ValidationError
from app.services.slides.interface import SlideParser
from app.services.slides.pdf_parser import PdfSlideParser
from app.services.slides.pptx_parser import PptxSlideParser


def get_slide_parser(mime_type: str) -> SlideParser:
    """Return the correct SlideParser for the given canonical MIME type.

    Raises ValidationError for unsupported types — callers must handle this
    before touching the network or storage.
    """
    if mime_type == "application/pdf":
        return PdfSlideParser()
    if mime_type in (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
    ):
        return PptxSlideParser()
    raise ValidationError(f"Unsupported slide format: {mime_type}")
