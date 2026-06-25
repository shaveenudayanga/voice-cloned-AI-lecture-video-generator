# ADR-0002 — Choose F5-TTS as Primary TTS Engine

**Status:** Accepted  
**Date:** 2026-06-25

## Context

The core product feature is voice cloning — synthesizing lecture narration in the professor's own voice from a short reference clip. We evaluated F5-TTS (SWivid/F5-TTS, CC-BY-NC-4.0) and XTTS-v2 (Coqui/idiap fork, CPML). Both are non-commercial only, which is compatible with our educational self-hosted use case (documented in `docs/LICENSE_AUDIT.md`).

## Decision

Use **F5-TTS `==1.1.20`** as the primary engine. XTTS-v2 is the automatic fallback (loaded only if F5-TTS fails at startup). The brief originally said "latest from SWivid/F5-TTS" — we pin to `==1.1.20` to comply with our own version-discipline principle (§2 rule 11). The `coqui-tts` package used for XTTS-v2 is the **idiap community fork** on PyPI (`coqui-tts`, not the archived `TTS` package).

**XTTS-v2 workaround:** PyTorch ≥2.6 restricts `torch.serialization` for arbitrary classes. XTTS-v2 weight files embed config classes; we allowlist them via `torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig])`. This workaround is encapsulated entirely in `services/tts/xtts_adapter.py`.

## Consequences

- F5-TTS produces high-quality clones from short (~10–60s) reference clips.
- CC-BY-NC-4.0 and CPML licenses must be documented in `LICENSE_AUDIT.md` and CI must fail if they go stale.
- Swapping either engine for a future model requires only changes inside `services/tts/` — no other layer is affected (§2 rule 2).
