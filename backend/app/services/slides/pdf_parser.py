# SPDX-License-Identifier: Apache-2.0

import structlog

from app.services.slides.interface import ParsedSlide

logger = structlog.get_logger(__name__)


class PdfSlideParser:
    """PDF → PNG using PyMuPDF (AGPL; self-hosted use is compliant)."""

    # Resolution for slide renders — 150 DPI is enough for readable video frames
    DPI = 150

    async def parse(self, source_bytes: bytes) -> list[ParsedSlide]:
        import fitz  # PyMuPDF — imported lazily to keep worker startup fast when unused

        doc = fitz.open(stream=source_bytes, filetype="pdf")
        slides: list[ParsedSlide] = []
        matrix = fitz.Matrix(self.DPI / 72, self.DPI / 72)

        for i, page in enumerate(doc):
            pixmap = page.get_pixmap(matrix=matrix)
            slides.append(
                ParsedSlide(
                    order_index=i,
                    image_png=pixmap.tobytes("png"),
                    extracted_text=page.get_text("text").strip(),
                )
            )

        logger.info("pdf_parsed", pages=len(slides))
        return slides
