# SPDX-License-Identifier: Apache-2.0
import asyncio
import tempfile
from pathlib import Path

import structlog

from app.services.slides.interface import ParsedSlide
from app.services.slides.pdf_parser import PdfSlideParser

logger = structlog.get_logger(__name__)


class PptxSlideParser:
    """PPTX → PDF via headless LibreOffice, then PDF → PNG via PdfSlideParser."""

    async def parse(self, source_bytes: bytes) -> list[ParsedSlide]:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            pptx_path = tmp / "input.pptx"
            pptx_path.write_bytes(source_bytes)

            # LibreOffice is embedded in the CPU worker image (not a separate service)
            proc = await asyncio.create_subprocess_exec(
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp),
                str(pptx_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                raise RuntimeError(f"LibreOffice conversion failed (exit {proc.returncode}): {stderr.decode()}")

            pdf_path = tmp / "input.pdf"
            if not pdf_path.exists():
                raise RuntimeError("LibreOffice did not produce output.pdf")

            pdf_bytes = pdf_path.read_bytes()
            logger.info("pptx_converted_to_pdf", size=len(pdf_bytes))

        return await PdfSlideParser().parse(pdf_bytes)
