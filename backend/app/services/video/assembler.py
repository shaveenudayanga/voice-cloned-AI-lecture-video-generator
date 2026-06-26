# SPDX-License-Identifier: Apache-2.0
"""
ffmpeg video assembler. Each slide image is shown for exactly the duration of its audio clip.
All ffmpeg/ffprobe calls use subprocess with list args — never shell=True.
"""
import asyncio
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import structlog

from app.domain.exceptions import VideoAssemblyError

logger = structlog.get_logger(__name__)

# Timeout constants (seconds)
_SEGMENT_TIMEOUT = 300
_CONCAT_TIMEOUT = 600


@dataclass
class SlideAudioPair:
    order_index: int
    image_path: Path
    audio_path: Path
    script_text: str
    duration_seconds: float


@dataclass
class AssemblyResult:
    output_path: Path
    srt_path: Path
    total_duration_seconds: float
    ffmpeg_version: str


def _get_ffmpeg_version() -> str:
    """Return the first line of `ffmpeg -version` output."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=15,
        )
        first_line = result.stdout.decode("utf-8", errors="replace").splitlines()[0]
        return first_line
    except Exception as exc:
        return f"unknown ({exc})"


def _run_ffmpeg(cmd: list[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


class VideoAssembler:
    """Assembles a list of (slide PNG, audio WAV) pairs into a single MP4 via ffmpeg."""

    def __init__(self, use_hwaccel: bool = False) -> None:
        self._use_hwaccel = use_hwaccel

    async def assemble(
        self,
        slides: list[SlideAudioPair],
        output_path: Path,
        srt_output_path: Path,
    ) -> AssemblyResult:
        """Run ffmpeg assembly in a thread pool so the event loop stays unblocked."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._assemble_sync,
            slides,
            output_path,
            srt_output_path,
        )

    def _assemble_sync(
        self,
        slides: list[SlideAudioPair],
        output_path: Path,
        srt_output_path: Path,
    ) -> AssemblyResult:
        ffmpeg_version = _get_ffmpeg_version()
        total_duration = 0.0

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            segment_paths: list[Path] = []

            for pair in sorted(slides, key=lambda p: p.order_index):
                seg_path = tmp / f"seg_{pair.order_index:04d}.mp4"
                self._encode_segment(pair, seg_path)
                segment_paths.append(seg_path)
                total_duration += pair.duration_seconds

            # Write concat list
            concat_file = tmp / "concat.txt"
            concat_file.write_text(
                "\n".join(f"file '{p}'" for p in segment_paths),
                encoding="utf-8",
            )

            # Concatenate segments
            concat_cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path),
            ]
            concat_result = _run_ffmpeg(concat_cmd, _CONCAT_TIMEOUT)
            if concat_result.returncode != 0:
                stderr = concat_result.stderr.decode("utf-8", errors="replace")
                raise VideoAssemblyError(f"ffmpeg concat failed:\n{stderr}")

        # Generate SRT alongside (pure Python — no subprocess)
        from app.services.video.srt_generator import generate_srt

        srt_content = generate_srt(slides)
        srt_output_path.write_text(srt_content, encoding="utf-8")

        logger.info(
            "video_assembled",
            slide_count=len(slides),
            total_duration_s=total_duration,
            output=str(output_path),
            ffmpeg_version=ffmpeg_version,
        )
        return AssemblyResult(
            output_path=output_path,
            srt_path=srt_output_path,
            total_duration_seconds=total_duration,
            ffmpeg_version=ffmpeg_version,
        )

    def _encode_segment(self, pair: SlideAudioPair, seg_path: Path) -> None:
        """Encode one (slide PNG + audio WAV) → MP4 segment."""
        cmd: list[str] = ["ffmpeg", "-y"]

        if self._use_hwaccel:
            cmd += ["-hwaccel", "auto"]

        cmd += [
            "-loop", "1",
            "-i", str(pair.image_path),
            "-i", str(pair.audio_path),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-vf", (
                "scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
            ),
            "-shortest",
            str(seg_path),
        ]

        result = _run_ffmpeg(cmd, _SEGMENT_TIMEOUT)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise VideoAssemblyError(
                f"ffmpeg segment {pair.order_index} failed:\n{stderr}"
            )
