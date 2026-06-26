# SPDX-License-Identifier: Apache-2.0
"""SRT subtitle generator. Timing is cumulative; each entry starts where the previous ended."""
from app.services.video.assembler import SlideAudioPair


def _fmt_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
    total_ms = round(seconds * 1000)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(slides: list[SlideAudioPair]) -> str:
    """Return SRT subtitle content for the ordered slide list.

    Each entry spans the full audio duration of that slide. Timings are cumulative —
    entry N starts exactly where entry N-1 ended.
    """
    ordered = sorted(slides, key=lambda p: p.order_index)
    entries: list[str] = []
    offset = 0.0

    for i, pair in enumerate(ordered, start=1):
        start = _fmt_srt_time(offset)
        end = _fmt_srt_time(offset + pair.duration_seconds)
        entries.append(f"{i}\n{start} --> {end}\n{pair.script_text}")
        offset += pair.duration_seconds

    return "\n\n".join(entries) + "\n"
