# ADR-0001 — Record Architecture Decisions Using ADRs

**Status:** Accepted  
**Date:** 2026-06-25

## Context

We need a lightweight, durable way to record the reasoning behind significant architectural decisions so that future contributors understand *why* things are the way they are, not just *what* they are. Git history captures what changed; ADRs capture why.

## Decision

Use Architecture Decision Records (ADRs) stored as Markdown files in `docs/adr/`. Each ADR is numbered sequentially, never deleted (superseded ADRs are marked as such), and committed in the same PR as the code change it documents. Format: status, context, decision, consequences.

## Consequences

- Future contributors can trace any structural decision to its rationale.
- ADRs accumulate as the project matures — the directory becomes a project history.
- Superseded ADRs are kept with a "Superseded by ADR-XXXX" note so the evolution is traceable.
