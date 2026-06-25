# ADR-0010 — Voice Recording Does Double Duty: Clone + Whisper Style Reference

**Status:** Accepted  
**Date:** 2026-06-25

## Context

A naive implementation feeds the voice recording only to the TTS model (F5-TTS), which controls *how words sound* — timbre, pace, intonation. But the professor wants scripts that sound like *him* in word choice too, not just in voice. The TTS model cannot make "which words" match his vocabulary — it only controls audio.

## Decision

A single ~60-second recording feeds **two independent systems**:

1. **Audio → F5-TTS voice clone:** captures timbre, pace, intonation. This is the reference clip.
2. **Audio → faster-whisper → transcript → LLM style reference:** captures vocabulary, sentence structure, register, grammar. Injected into every `script_generation` prompt.

`faster-whisper` runs locally (MIT license, free, no API cost) on the same GPU worker using the `base` model (sufficient for clean 60-second clips). The transcript is persisted on the `VoiceProfile` as `style_reference_transcript`. The `voice_ingestion` task performs both storage and transcription. The user may also supply an additional `extra_style_sample` (pasted transcript, lecture notes) on the `VoiceProfile`.

**Critical invariant:** the script generator must *always* receive the style reference — never just the slide. See §10 anti-patterns.

## Consequences

- `VoiceProfile` stores `style_reference_transcript` (non-null after ingestion) and `extra_style_sample` (nullable).
- `script_generation` task receives `voice_profile_id`; it is responsible for fetching the transcript from the repository.
- The `Transcriber` interface in `services/transcription/` is swappable (e.g., future local Whisper v3 large, or cloud ASR) without changing the task layer.
- On 4 GB VRAM machines: Whisper and F5-TTS must not be loaded simultaneously (controlled by `VRAM_BUDGET_GB`).
