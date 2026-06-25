# ADR-0011 — Gemini 2.5 Flash as Default LLM; Ollama as Local Fallback

**Status:** Accepted  
**Date:** 2026-06-25

## Context

Script generation requires a multimodal LLM that can see the slide image, not just extracted text. We need a provider with a generous free tier (the professor is self-hosting, zero budget for LLM costs), stable multimodal support, and a well-maintained Python SDK.

## Decision

- **Default:** `gemini-2.5-flash` via `google-genai` SDK `^1.0`. Generous free tier, stable multimodal API, good instruction-following for JSON output schemas.
- **Local fallback:** `qwen2.5-vl:7b` via Ollama when `LLM_PROVIDER=ollama`. Zero API dependency; runs on the same GPU; good multimodal quality for a 7B model.

Switching providers requires only an env-var change (`LLM_PROVIDER`). The `LLMScriptGenerator` protocol in `services/script/interface.py` ensures no endpoint or task code knows which provider is active. Prompts are versioned in `docs/prompts/` as plain Markdown — never inline in code (§10 anti-patterns).

`GEMINI_API_KEY` is documented-but-optional. Integration tests skip gracefully with `pytest.skip("GEMINI_API_KEY not set")` when the key is absent — CI never fails for a missing API key.

## Consequences

- Gemini model updates (e.g., `gemini-3-flash` opt-in) are env-var changes, not code changes.
- Prompt format is versioned; prompt changes should increment the version in `docs/prompts/` and update the corresponding test fixture.
- If Gemini free tier changes, switching to Ollama is a one-line env change.
