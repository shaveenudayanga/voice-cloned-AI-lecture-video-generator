# LectureVoice — Phase Progress Log

Summaries written retroactively from git history (commits b5c603a through 935cf71).
Each entry covers what was delivered, final test/lint/typecheck numbers, and any
notable decision or fix made during that phase.

---

## Phase 1 — Foundations (2026-06-25, commit b5c603a)

Full project skeleton: FastAPI backend, Next.js 16 frontend, Docker Compose stack
(PostgreSQL 17, Valkey 8, SeaweedFS), CI workflows for backend, frontend, and license
audit. Typed config via `pydantic-settings`, API-key auth, `structlog` JSON logging,
OpenTelemetry setup, and all service/task stubs with correct interfaces. ADRs 0001–0012
committed. `uv.lock` and `pnpm-lock.yaml` committed.

**Acceptance numbers (Phase 1+2 combined commit):** 24 unit tests passing, `make lint`
and `make typecheck` (mypy --strict + tsc --strict) clean.

---

## Phase 2 — Slide Ingestion (2026-06-25, commit b5c603a)

Upload endpoint with magic-byte MIME sniffing and 50 MB size cap. PDF parser
(PyMuPDF), PPTX parser (LibreOffice headless), `SlideParser` protocol, S3-compatible
blob-store adapter for SeaweedFS. ORM models + repositories for `Slide` and `Job`.
Alembic migration `0001_add_slides_and_jobs`. Idempotent `slide_ingestion` Celery task
with per-slide progress. Integration test validates N-slide PDF and PPTX paths.

**Acceptance numbers:** 24 passing, 0 slow-skipped; ruff and mypy --strict clean.

---

## Phase 3 — Voice Profiles & Transcription (2026-06-26, commit ae6c36d)

`VoiceProfile` + `Project` ORM models, repositories, and full CRUD endpoints.
`UserIdDep` derives a stable user UUID via `uuid5(NAMESPACE_OID, api_key)` so no
separate user table is required at this stage. Audio MIME sniffer (WAV/MP3/OGG/WebM/MP4)
with magic-byte detection. `WhisperAdapter` with VRAM budget check (CPU fallback < 6 GB)
and `TranscriptionError` wrapping. `voice_ingestion` Celery task with real Whisper
transcription. `voice_preview` stub. Alembic migration `0002`.

Notable decision: VRAM budget check at transcription time avoids OOM on the RTX 3050 Ti
dev machine (4 GB VRAM) — Whisper and F5-TTS cannot both reside in VRAM simultaneously.

**Acceptance numbers:** 34 passing, 1 slow-skipped; ruff and mypy --strict clean.

---

## Phase 4 — Script Generation (style-aware) (2026-06-26, commit c4da600)

`LLMScriptGenerator` protocol, Gemini + Ollama adapters with markdown-artifact
validation and one-retry logic on malformed output. Versioned prompt template loaded
from `docs/prompts/script_generation_v1.md` (style-reference transcript injected into
prompt). `Script` entity/ORM/repository with SHA-256 cache-skip fingerprint. Three
REST endpoints: fan-out generate, list, PATCH. Idempotent `script_generation` Celery
task. Alembic migration `0003`.

**Acceptance numbers:** 45 passing, 2 slow/integration-skipped; ruff clean; mypy
--strict 81 files; tsc --strict clean.

---

## Phase 5 — TTS Engine & Voice Preview (2026-06-26, commit 61da64c)

Full TTS synthesis pipeline. `model_manager.py` handles process-local VRAM lifecycle —
evicts Whisper before loading TTS (and vice versa) when `VRAM_BUDGET_GB < 6.0`; FP16
mandatory for F5-TTS on CUDA. `F5TTSAdapter` + `XTTSAdapter` with Path-based I/O.
CUDA OOM caught with CPU fallback (logged as warning). `AudioClip` entity redesigned
with `synthesis_fingerprint` for cache-skip. `tts_synthesis` task with per-slide
fingerprint cache-skip. `voice_preview` task replaces Phase 3 stub. Alembic
migration `0004`.

Notable decision: the `TTSEngine` protocol was redesigned mid-phase from stream-based
to `Path`-based I/O to avoid holding large WAV buffers in memory on low-VRAM devices.

**Acceptance numbers:** 58 passing, 3 slow/GPU-skipped; mypy --strict and ruff clean.

---

## Phase 6 — Video Assembly (2026-06-26, commit a21b6da)

`VideoAssembler` produces MP4 via `ffmpeg` subprocess (list args only, never
`shell=True`). Each slide displayed for exactly the duration of its audio clip.
`SRTGenerator` produces subtitle side-artifact from cumulative script timings.
`VideoArtifact` entity with `slide_count` and `ffmpeg_version`. `VideoArtifactModel` +
repository. Alembic migration `0005`. `POST`/`GET` `/api/v1/projects/{id}/video/`
endpoints. `probe.get_audio_duration` uses `ffprobe` primary, `wave` module fallback.
`FFMPEG_HWACCEL` defaults `false` so the default path works on any machine.

**Acceptance numbers:** 73 passing, 4 slow-skipped; mypy --strict and ruff clean.

---

## Phase 7 — Frontend: Wizard (2026-06-27, commits 9c7c9ba + f3f497c)

Full back-navigable stepper backed by a project state machine. Dashboard "Create new
lecture video" → auto-creates project → enters wizard. Steps: Upload → Voice (pick
saved profile or record ~60s, voice preview) → Scripts (SSE-driven per-slide progress,
then editor) → Audio (per-slide playback, change-voice/change-scripts) → Render →
Done (Download/Save-to-folder honoring `DEPLOYMENT_MODE`). `VoiceRecorder` component
with MediaRecorder capture, level meter, and playback. `JobProgress` SSE-driven progress
bars.

Notable fix (commit 9c7c9ba): ESLint errors were introduced during Phase 7 — the
fix commit resolved `no-use-before-define` in `VoiceRecorder`, sync `setState` in
effects in `ScriptsStep`/`RenderStep`, `use-blob-url`, and stale `eslint-disable`
directives. Backend: `health.py` type annotation fix; blob proxy endpoint added.

**Acceptance numbers (post-fix):** 82 backend + 36 frontend passing; `make lint`
0 errors 0 warnings; mypy --strict + tsc --strict clean.

---

## Phase 8 — Per-Slide Script Editor (2026-06-27, commit 2e23553)

Two-pane `SlideEditor` component: left pane = slide image with zoom + prev/next,
right pane = editable textarea with explicit per-slide Save, pronunciation-hints
field, "Regenerate this slide" button, and "Preview audio (this slide)" that
synthesises just the current slide and plays it inline. Unsaved-changes confirmation
dialog on slide navigation. Stable `useRef` refs for keyboard handler. Backend:
`PATCH /scripts/{id}` endpoint, `POST /audio/{slideId}/synthesize` per-slide endpoint,
`GET /audio/` list endpoint, and 348-line unit test suite. Frontend: 237-line Vitest
component test suite.

**Acceptance numbers:** 82 backend + 36 frontend passing.
Lint and typecheck clean at the time of the Phase 9 / `f3f497c` consolidation commit.

---

## Phase 9 — Observability & Hardening (2026-06-30, commit 672f562)

Correlation IDs: `CorrelationIDMiddleware` generates/echoes `X-Request-ID`; `ContextVar`
flows through HTTP → structlog processor → Celery `task_prerun` signal. Prometheus
metrics: `http_requests_total`, `http_request_duration_seconds`,
`celery_task_total/duration`, `queue_depth`, TTS cache hit/miss, `llm_generation_total`;
`GET /metrics` endpoint. OTel: FastAPI + SQLAlchemy + httpx auto-instrumentation; OTLP
or stdout exporter. Rate limiting: `slowapi` with `X-API-Key` key func; upload 10/min,
generate 20/min, default 100/min. Full domain-exception → HTTP status code mapping;
every 4xx/5xx response body includes `request_id`. `scripts/backup.sh` and
`docs/runbook.md` (all 10 required operational sections).

**Acceptance numbers:** 97 passing, mypy --strict and ruff clean.
8 new Phase 9 unit tests.

---

## Phase 10 — Polish & Release (2026-06-30 + 2026-07-01, commits c2d3762 + 935cf71)

README rewritten for a non-engineer audience with step-by-step setup and accurate
first-run time estimate. `make install`, `make first-run`, `make release` Makefile
targets. `CHANGELOG.md` and `VERSION` (0.1.0) added. Sample content: 5-slide
photosynthesis PDF + voice recording guide. Playwright E2E download-flow test.
Production compose overlay updates. License audit refreshed.

Critical fix (commit 935cf71): the backend `Dockerfile` only copied `app/` into the
image, leaving `alembic.ini` behind. `make first-run` migrations failed silently
because the error was swallowed by `|| true`. Fix: `COPY alembic.ini` added to
`Dockerfile`; `|| true` removed so migration failures abort the install visibly.

**Acceptance numbers:** Full stack smoke-tested via `make first-run` on a clean clone.
Lint, typecheck, and license audit clean.

---

*Going forward: add a new entry to this file at the end of each completed phase,
before closing the phase PR.*
