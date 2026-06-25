# ADR-0005 — Replace Redis with Valkey 8 as Message Broker

**Status:** Accepted  
**Date:** 2026-06-25

## Context

Redis Inc. changed its license from BSD to SSPL + RSALv2 in 2024, creating uncertainty for downstream projects that redistribute or build services on top of Redis. Redis 7.4+ and Redis 8 are under this dual license. For a self-hosted open-source project that may be forked or redistributed, SSPL creates risk.

## Decision

Use **Valkey 8.x** (Linux Foundation, BSD-3-Clause) as the Celery broker and result backend. Valkey is a hard fork of Redis 7.2.4 created by the Linux Foundation after the license change. It is wire-compatible with Redis (RESP2/RESP3), so `redis-py 5.2.1` and Celery work unchanged. The image is `valkey/valkey:8-alpine`.

## Consequences

- BSD-3-Clause is clean for any use including redistribution.
- Zero application code changes vs. Redis — the broker URL changes from `redis://` to `redis://` (same scheme, wire-compatible).
- `redis-py` is still named `redis` on PyPI; there is no `valkey-py` package needed.
- If Valkey ever diverges from Redis in breaking ways, the Celery broker URL and `redis-py` client are the only things that would need updating.
