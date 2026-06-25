# ADR-0008 — Python as Orchestrator; No Non-Python Rewrite Without Benchmark

**Status:** Accepted  
**Date:** 2026-06-25

## Context

The hot path in this system (TTS, PDF rendering, ffmpeg assembly) runs inside C/C++/CUDA workers — Python is the glue. Total Python-glue overhead across a 30-slide deck is estimated at 0.5–2 seconds of a 3–8 minute total job. A language rewrite would save fractions of a percent while discarding the Python ML ecosystem (PyTorch, F5-TTS, faster-whisper, PyMuPDF) the entire product depends on.

## Decision

Python is the correct orchestrator language. **No component may be rewritten in another language for performance reasons** without: (1) exhausting optimization levers 1–5 in §1.2, and (2) presenting a benchmark in an ADR proving the Python glue is the actual bottleneck.

The five levers in priority order:
1. Warm GPU worker (load TTS model once at startup, not per task)
2. Parallel per-slide workers (`--scale worker-gpu=N`)
3. Better GPU hardware
4. FP16/INT8 quantization of the TTS model
5. Content-hash cache-skip (skip synthesis when `(script_hash, voice_profile_id, tts_params)` is unchanged)

On the RTX 3050 Ti (4 GB VRAM) development machine, levers 1 and 4 are mandatory, not optional.

## Consequences

- This decision is binding. Any proposal to rewrite a component in Rust/C++ must cite this ADR and include the benchmark.
- The warm-worker pattern (lever 1) is a Phase 5 acceptance criterion, not a nice-to-have.
