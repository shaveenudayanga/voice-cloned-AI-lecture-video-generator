# SPDX-License-Identifier: Apache-2.0
"""
Magic-byte MIME detection for voice recording uploads.

We do not trust the Content-Type header or file extension alone.
Bytes checked:
  WAV:  b"RIFF" at 0:4 and b"WAVE" at 8:12
  OGG:  b"OggS" at 0:4
  WebM: b"\x1a\x45\xdf\xa3" at 0:4
  MP3:  b"ID3" at 0:3, or 0xFF sync byte at [0] with 0xFB/F3/F2/FA at [1]
  MP4 audio: b"ftyp" at 4:8 combined with an accepted declared Content-Type
"""

_WAV_RIFF = b"RIFF"
_WAV_WAVE = b"WAVE"
_OGG_MAGIC = b"OggS"
_WEBM_MAGIC = b"\x1a\x45\xdf\xa3"
_MP3_ID3 = b"ID3"
_MP3_SYNC_BYTES = frozenset({0xFB, 0xF3, 0xF2, 0xFA})
_FTYP = b"ftyp"

_ACCEPTED_MP4_TYPES = frozenset({"audio/mp4", "audio/x-m4a"})
_ACCEPTED_ALL = frozenset({
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/ogg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/webm",
})


def sniff_audio_mime(header: bytes, declared_content_type: str) -> str | None:
    """Return canonical audio MIME type or None if unsupported/mismatched.

    Requires at least 12 bytes to detect WAV reliably.
    """
    # WAV: RIFF header + WAVE marker at offset 8
    if header[:4] == _WAV_RIFF and len(header) >= 12 and header[8:12] == _WAV_WAVE:
        return "audio/wav"
    # OGG container
    if header[:4] == _OGG_MAGIC:
        return "audio/ogg"
    # WebM container
    if header[:4] == _WEBM_MAGIC:
        return "audio/webm"
    # MP3: ID3 tag header
    if header[:3] == _MP3_ID3:
        return "audio/mpeg"
    # MP3: raw MPEG sync frame (no ID3 tag)
    if len(header) >= 2 and header[0] == 0xFF and header[1] in _MP3_SYNC_BYTES:
        return "audio/mpeg"
    # MP4 audio: ISO Base Media container — ftyp box at offset 4
    if len(header) >= 8 and header[4:8] == _FTYP and declared_content_type in _ACCEPTED_MP4_TYPES:
        return "audio/mp4"
    return None
