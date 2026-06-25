# SPDX-License-Identifier: Apache-2.0
"""
Magic-byte MIME detection for slide uploads.

We do not trust the Content-Type header or file extension alone.
Read the first ~8 bytes to identify the true format.

PDF:  starts with b'%PDF'
PPTX: PK ZIP archive (b'PK\x03\x04') — further validated by the factory
      which passes the PPTX MIME type only when the upstream Content-Type
      also claims PPTX (double-check: magic bytes + declared type).
"""

PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"

PPTX_CONTENT_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
    }
)


def sniff_mime(header: bytes, declared_content_type: str) -> str | None:
    """
    Return the canonical MIME type or None if the format is unsupported/mismatched.

    Strategy:
    - PDF: magic bytes must be %PDF, regardless of declared type.
    - PPTX: magic bytes must be PK (ZIP) AND declared type must be a PPTX variant
      (PPTX is a ZIP; we cannot distinguish it from DOCX/XLSX by bytes alone).
    """
    if header[:4] == PDF_MAGIC:
        return "application/pdf"
    if header[:4] == ZIP_MAGIC and declared_content_type in PPTX_CONTENT_TYPES:
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return None
