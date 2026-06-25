# ADR-0007 — Web-First Delivery; Tauri Desktop Wrap Deferred to Phase 11

**Status:** Accepted  
**Date:** 2026-06-25

## Context

The professor may run this on a personal PC (GPU local, voice stays on machine) or on a lab server (shared, browser-based). Both use cases are valid and we cannot choose one yet. Electron is too heavy; a native rewrite is too expensive.

## Decision

Build a **web application** (FastAPI + Next.js + Docker). Wrap as a **Windows desktop app via Tauri** in Phase 11 only if needed. The stack is already a web app — Tauri provides a thin Rust-based shell that loads the existing frontend and bundles the backend as a local process.

**The single behavioral difference is abstracted behind one env flag:**

| `DEPLOYMENT_MODE` | Output step behavior |
|---|---|
| `web` (default) | "Download video" button streams MP4 from storage to browser |
| `desktop` | "Save to folder" uses Tauri native filesystem API |

`lib/deployment.ts` is the **only** place in the frontend that reads `DEPLOYMENT_MODE`. No other file may branch on this value. The Tauri packaging in Phase 11 must not require any changes to `frontend/app/` or `frontend/components/` beyond the single output-step branch already present.

## Consequences

- One codebase serves both delivery models.
- Phase 11 is purely a packaging concern — it cannot become a refactor.
- A diff of `frontend/app` between Phase 10 and Phase 11 showing more than the output-step branch is a signal that this ADR was violated.
