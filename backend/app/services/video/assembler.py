# SPDX-License-Identifier: Apache-2.0
"""
ffmpeg video assembler. Each slide image is shown for exactly the duration of its audio clip.
ffmpeg is called via subprocess with list args — never shell=True with user-supplied input.
"""
import asyncio
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import structlog

from app.domain.exceptions import VideoAssemblyError

logger = structlog.get_logger(__name__)


@dataclass
class SlideAudioPair:
    slide_png: bytes
    audio_wav: bytes
    duration_s: float


async def assemble_video(pairs: list[SlideAudioPair]) -> tuple[bytes, str]:
    """
    Assemble ordered (slide PNG, audio WAV) pairs into an MP4.
    Returns (mp4_bytes, srt_content).
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _assemble_sync, pairs)


def _assemble_sync(pairs: list[SlideAudioPair]) -> tuple[bytes, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        concat_lines: list[str] = []
        srt_entries: list[str] = []
        cumulative_s = 0.0

        for i, pair in enumerate(pairs):
            img_path = tmp / f"slide_{i:04d}.png"
            wav_path = tmp / f"audio_{i:04d}.wav"
            seg_path = tmp / f"seg_{i:04d}.mp4"

            img_path.write_bytes(pair.slide_png)
            wav_path.write_bytes(pair.audio_wav)

            # Build a silent video of exactly duration_s from the still image + audio
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(img_path),
                "-i", str(wav_path),
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "128k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                "-hwaccel", "auto",
                str(seg_path),
            ]
            result = _run(cmd)
            if result.returncode != 0:
                raise VideoAssemblyError(
                    f"ffmpeg segment {i} failed: {result.stderr.decode()}"
                )

            concat_lines.append(f"file '{seg_path}'")

            # SRT entry
            start = _fmt_srt_time(cumulative_s)
            end = _fmt_srt_time(cumulative_s + pair.duration_s)
            srt_entries.append(f"{i + 1}\n{start} --> {end}\n(slide {i + 1})\n")
            cumulative_s += pair.duration_s

        concat_file = tmp / "concat.txt"
        concat_file.write_text("\n".join(concat_lines))
        output_path = tmp / "output.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path),
        ]
        result = _run(cmd)
        if result.returncode != 0:
            raise VideoAssemblyError(f"ffmpeg concat failed: {result.stderr.decode()}")

        mp4_bytes = output_path.read_bytes()
        srt_content = "\n".join(srt_entries)
        logger.info("video_assembled", slides=len(pairs), duration_s=cumulative_s, size=len(mp4_bytes))
        return mp4_bytes, srt_content


def _run(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, capture_output=True)


def _fmt_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
