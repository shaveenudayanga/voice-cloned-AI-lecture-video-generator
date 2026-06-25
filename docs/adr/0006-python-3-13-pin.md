# ADR-0006 — Pin Python to 3.13.x

**Status:** Accepted  
**Date:** 2026-06-25

## Context

Three load-bearing dependencies form a triangle that determines the Python version:
- **Celery 5.6.3** supports Python 3.9–3.13. Python 3.14 is explicitly unsupported.
- **PyTorch 2.11.0** has first-class wheels for 3.13 and 3.14.
- **F5-TTS 1.1.20** requires Python 3.10+ and works on 3.13.

Python 3.13 is the only version where all three are simultaneously supported and stable. Python 3.12 would work but is one minor behind the current stable. Python 3.14 is blocked by Celery.

## Decision

Pin Python to **`>=3.13,<3.14`** in `pyproject.toml`. Docker images use `python:3.13-slim` (CPU) and a Python 3.13 install on `nvidia/cuda:12.4.1-runtime-ubuntu22.04` (GPU). Host Python may be any version — application code runs exclusively in Docker containers.

**PyTorch pin:** `torch==2.11.0`. PyTorch 2.12 released 2026-05-13 — only one patch cycle old at the time of this decision (2026-06-25). We apply our "last well-shaken-out minor" rule.

> Upgrade path: reconsider torch at `2.12.2+`. Reconsider Python 3.14 when Celery 5.7 ships (est. Q3 2026).

## Consequences

- Any future Python upgrade requires checking: PyTorch wheels, Celery support, F5-TTS deps, coqui-tts wheels, asyncpg wheels, PyMuPDF wheels (§5.1 constraint table).
- Host Python version (currently 3.12.3) does not block Phase 1–10 — `make check-env` warns but does not error.
