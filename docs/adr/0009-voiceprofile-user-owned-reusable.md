# ADR-0009 — VoiceProfile is User-Owned and Reusable Across Projects

**Status:** Accepted  
**Date:** 2026-06-25

## Context

Early designs tied the voice recording to a single project. The professor would have to re-record for every new lecture. Recording, running Whisper transcription, and confirming clone quality takes several minutes — repeating it every time is the primary adoption blocker.

## Decision

`VoiceProfile` belongs to the **user**, not the project. A user may have multiple profiles (e.g., "English lecture voice", "casual"). Each project has a `voice_profile_id` FK that must be set at synthesis time. A `VoiceProfile.is_default` flag pre-fills the selector for new projects as a convenience — it does not constrain which profile a project uses.

The adoption-critical path — "upload slides, pick saved voice, go" — is explicitly tested in Phase 3 acceptance criteria.

Voice recordings are biometric data. They are stored in SeaweedFS under `users/{id}/voices/{profile_id}/` and are never logged, never sent to any third party, and never tied to a project's storage path. Deletion of a `VoiceProfile` removes its blob from storage and is blocked (or soft-handled) if any project still references it.

## Consequences

- `Project` has a `voice_profile_id` FK (nullable until voice step is completed).
- `VoiceProfile` is scoped to `user_id`, never to `project_id`.
- The `voices/` UI page manages profiles independently of any project.
- All synthesis tasks receive `voice_profile_id` as an argument, not a blob key directly.
