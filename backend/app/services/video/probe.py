# SPDX-License-Identifier: Apache-2.0
"""Audio/video duration probe. Uses ffprobe; falls back to Python wave for WAV files."""
import json
import subprocess
import wave
from pathlib import Path


def get_audio_duration(audio_path: Path) -> float:
    """Return duration in seconds for a WAV (or any audio) file.

    Primary: ffprobe via subprocess with list args.
    Fallback: Python wave module (WAV only) if ffprobe is unavailable or fails.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(audio_path),
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
    except (FileNotFoundError, subprocess.TimeoutExpired, KeyError, ValueError, json.JSONDecodeError):
        pass

    # Fallback: wave module (WAV only)
    with wave.open(str(audio_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)
