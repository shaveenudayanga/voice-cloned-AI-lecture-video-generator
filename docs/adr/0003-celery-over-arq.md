# ADR-0003 — Choose Celery Over ARQ as the Task Queue

**Status:** Accepted  
**Date:** 2026-06-25

## Context

Long-running TTS synthesis, script generation, slide ingestion, and video assembly must run in background workers with retry, progress reporting, and idempotency. We evaluated Celery 5.6 and ARQ (async Redis queue).

## Decision

Use **Celery 5.6.3** with Valkey as broker and result backend.

Reasons:
- Celery has mature retry semantics (`autoretry_for`, `acks_late`, `reject_on_worker_lost`) that match our reliability requirements out of the box.
- Task routing to named queues (`cpu`, `gpu`) is straightforward.
- ARQ is simpler but lacks built-in retry policies, canvas primitives (chord for per-slide fan-out), and the operational tooling (Flower, CLI) that matters for a maintainable system.

## Consequences

- Python is constrained to ≤3.13 until Celery 5.7 adds 3.14 support (see ADR-0006).
- `redis-py` is pinned to `==5.2.1` (Celery 5.6 constraint). This works unchanged against Valkey 8.x (wire-compatible).
- Re-evaluate ARQ or Dramatiq if Celery's dependency footprint becomes a problem in future phases.
