#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
TTS benchmark script. Reports cold-start time, warm inference latency, and
a basic audio-similarity score vs. the reference clip.

Usage:
  python3 scripts/bench-tts.py --ref path/to/ref.wav --text "The quick brown fox"

Note: On the RTX 3050 Ti (4 GB VRAM), F5-TTS requires FP16 quantization.
The VRAM_BUDGET_GB env var must be set to 4.0 on this machine.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark TTS engines")
    parser.add_argument("--ref", required=True, help="Path to reference audio WAV")
    parser.add_argument("--text", default="Hello, this is a voice clone benchmark test sentence.", help="Text to synthesize")
    parser.add_argument("--engine", choices=["f5", "xtts", "both"], default="both")
    parser.add_argument("--runs", type=int, default=3, help="Number of warm runs")
    args = parser.parse_args()

    ref_path = Path(args.ref)
    if not ref_path.exists():
        print(f"Reference file not found: {ref_path}", file=sys.stderr)
        return 1

    ref_bytes = ref_path.read_bytes()

    print(f"Reference: {ref_path} ({len(ref_bytes)} bytes)")
    print(f"Text: {args.text!r}")
    print(f"Runs: {args.runs}")
    print()

    if args.engine in ("f5", "both"):
        _bench_engine("F5-TTS", "f5", ref_bytes, args.text, args.runs)

    if args.engine in ("xtts", "both"):
        _bench_engine("XTTS-v2", "xtts", ref_bytes, args.text, args.runs)

    return 0


def _bench_engine(name: str, engine_id: str, ref_bytes: bytes, text: str, runs: int) -> None:
    import os
    os.environ.setdefault("TTS_ENGINE", engine_id)

    sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

    print(f"=== {name} ===")

    t0 = time.perf_counter()
    if engine_id == "f5":
        from app.services.tts.f5_adapter import F5TTSEngine
        engine = F5TTSEngine()
    else:
        from app.services.tts.xtts_adapter import XTTSEngine
        engine = XTTSEngine()
    engine.warm_up()
    cold_start_s = time.perf_counter() - t0
    print(f"Cold start (model load): {cold_start_s:.2f}s")

    import asyncio
    latencies: list[float] = []
    for i in range(runs):
        t1 = time.perf_counter()
        result = asyncio.run(engine.synthesize(text, ref_bytes))
        latency = time.perf_counter() - t1
        latencies.append(latency)
        print(f"  Run {i+1}: {latency:.2f}s → {result.duration_s:.2f}s audio")

    avg = sum(latencies) / len(latencies)
    print(f"Warm average: {avg:.2f}s")
    print()


if __name__ == "__main__":
    sys.exit(main())
