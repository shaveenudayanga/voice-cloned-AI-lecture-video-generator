#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
TTS benchmark script. Reports cold-start time, warm inference latency, VRAM usage,
and whether FP16 / GPU were active.

Usage:
  uv run python scripts/bench-tts.py --ref path/to/ref.wav
  uv run python scripts/bench-tts.py --ref path/to/ref.wav --engine f5 --runs 3

Note: On RTX 3050 Ti (4 GB VRAM) F5-TTS uses FP16.  Set VRAM_BUDGET_GB=4.0
or it will be read from config automatically.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

# Allow running from the repo root: `python scripts/bench-tts.py`
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark TTS engines (Phase 5 interface)")
    parser.add_argument("--ref", required=True, help="Path to reference audio WAV")
    parser.add_argument(
        "--text",
        default="Hello, this is a voice clone benchmark test sentence for LectureVoice.",
        help="Text to synthesize",
    )
    parser.add_argument("--engine", choices=["f5", "xtts", "both"], default="both")
    parser.add_argument("--runs", type=int, default=3, help="Number of warm runs")
    args = parser.parse_args()

    ref_path = Path(args.ref)
    if not ref_path.exists():
        print(f"Reference file not found: {ref_path}", file=sys.stderr)
        return 1

    print(f"Reference : {ref_path} ({ref_path.stat().st_size} bytes)")
    print(f"Text      : {args.text!r}")
    print(f"Runs      : {args.runs}")
    print()

    engines: list[str] = []
    if args.engine in ("f5", "both"):
        engines.append("f5")
    if args.engine in ("xtts", "both"):
        engines.append("xtts")

    for engine_id in engines:
        _bench_engine(engine_id, ref_path, args.text, args.runs)

    return 0


def _bench_engine(engine_id: str, ref_path: Path, text: str, runs: int) -> None:
    os.environ["TTS_ENGINE"] = engine_id

    # Reset model_manager state between engine benchmarks so we get an honest cold start
    import importlib
    import app.services.tts.model_manager as mm
    mm._tts_model = None  # noqa: SLF001
    mm._tts_slot_owner = None  # noqa: SLF001
    if "app.services.tts.model_manager" in sys.modules:
        importlib.reload(mm)

    engine_label = "F5-TTS (CC-BY-NC)" if engine_id == "f5" else "XTTS-v2 (CPML)"
    print(f"=== {engine_label} ===")

    # -- Cold start: first load triggers model download + init
    t0 = time.perf_counter()
    try:
        from app.services.tts.model_manager import load_tts_model, get_vram_free_gb
        load_tts_model()
        cold_start_s = time.perf_counter() - t0
        vram_free_after = get_vram_free_gb()
        if vram_free_after >= 0:
            print(f"Cold start  : {cold_start_s:.2f}s  (VRAM free after load: {vram_free_after:.2f} GB)")
        else:
            print(f"Cold start  : {cold_start_s:.2f}s  (no CUDA / CPU-only)")
    except Exception as exc:
        print(f"Cold start  : FAILED — {exc}")
        print()
        return

    # -- Warm runs
    if engine_id == "f5":
        from app.services.tts.f5_adapter import F5TTSAdapter
        adapter = F5TTSAdapter()
    else:
        from app.services.tts.xtts_adapter import XTTSAdapter
        adapter = XTTSAdapter()

    latencies: list[float] = []
    last_result = None
    for i in range(runs):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = Path(tmp.name)
        try:
            t1 = time.perf_counter()
            result = asyncio.run(adapter.synthesize(text, ref_path, out_path))
            latency = time.perf_counter() - t1
            latencies.append(latency)
            last_result = result
            rtf = latency / result.duration_seconds if result.duration_seconds > 0 else float("inf")
            print(
                f"  Run {i+1}: {latency:.2f}s → {result.duration_seconds:.2f}s audio  "
                f"RTF={rtf:.2f}x  gpu={result.used_gpu}"
            )
        except Exception as exc:
            print(f"  Run {i+1}: ERROR — {exc}")
        finally:
            out_path.unlink(missing_ok=True)

    if latencies:
        avg = sum(latencies) / len(latencies)
        print(f"Warm avg    : {avg:.2f}s")

    if last_result:
        print(f"Engine used : {last_result.engine_used}")
        print(f"GPU used    : {last_result.used_gpu}")
        print(f"FP16 active : {'yes (RTX 3050 Ti path)' if last_result.used_gpu else 'N/A (CPU)'}")
        print(f"CPU fallback: {'triggered' if not last_result.used_gpu else 'no'}")

    print()


if __name__ == "__main__":
    sys.exit(main())
