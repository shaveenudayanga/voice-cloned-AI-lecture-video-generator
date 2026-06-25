# SPDX-License-Identifier: Apache-2.0
import json
import subprocess
from pathlib import Path


def probe_duration(file_path: str | Path) -> float:
    """Return video/audio duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(file_path),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.decode()}")
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])
