# PROJECT BRIEF — LectureVoice
**A voice-cloned AI lecture video generator. Open-source, self-hostable, engineered to last.**

**Document version:** 2.1 — version-locked for May 2026, UX flow + delivery model finalized
**Effective stack date:** 2026-05-25

> You are a senior staff engineer joining this project on day one. Read this brief end-to-end before writing a single line of code. This document is the contract. If anything here is ambiguous, ask before assuming. If anything here is wrong or weak, push back with a reasoned alternative. Do not cargo-cult, do not vibe-code, do not skip the boring parts. We are building infrastructure, not a demo.

---

## 0. Changelog

### From v2.0 → v2.1 (UX flow + delivery model)
- Added §1.1 **Delivery model decision**: build the web app first; wrap as a Windows desktop app later with Tauri only if needed. Same codebase both ways. A single `DEPLOYMENT_MODE` flag (`web` | `desktop`) drives the one behavioral difference (download button vs. save-to-folder).
- Added a `VoiceProfile` entity (§3 data model): the voice recording belongs to the **user**, not the project. Record once, reuse for every future lecture. This is the adoption-critical feature.
- Added a **Whisper transcription** step on the voice recording (§3.5, Phase 3/4): the recording now does double duty — audio drives the voice clone, the transcript becomes a *style reference* fed to the script-generator LLM so the generated words match the professor's own vocabulary, phrasing, and grammar. This is what makes "his language style" actually work. The voice clone only controls how words *sound*, not *which* words — the transcript closes that gap.
- Added a **voice preview** step (§8 Phase 4, §9 Phase 7): after recording, synthesize one short test sentence immediately so a bad clone (bad mic, echo) is caught in seconds, not after 30 slides.
- Reframed the wizard (§8 Phases 6–7) as a **back-navigable stepper backed by a state machine**, not destroy-and-replace DOM. The professor can step back to fix one slide's script and regenerate only that slide's audio. All regeneration is **per-slide, never all-or-nothing**.
- Added §1.2 **Language/performance rationale**: Python is the orchestrator, not the bottleneck. The brief documents why, and what actually moves the needle (warm GPU worker, parallel workers, better GPU, FP16 quantization, caching) — none of which is a language rewrite.

### From v1.0 → v2.0 (versions + ecosystem)
- Pinned exact versions for every component in the stack (§4).
- Added §5 **Compatibility Matrix** — every cross-component constraint that determined the pins, with rationale.
- Replaced MinIO with **SeaweedFS** (MinIO Community Edition was archived Feb 2026; SeaweedFS is the Apache-2.0 successor adopted by Kubeflow). Storage interface is unchanged because of the adapter pattern — this is exactly why we have it.
- Replaced Redis with **Valkey 8** (Linux Foundation BSD-3 fork after Redis Inc.'s license change). Wire-compatible; the `redis-py` client and Celery work unchanged.
- Locked Python to **3.13.x** (not 3.14) because Celery 5.6 does not yet support 3.14.
- Locked Node.js to **24 LTS** (not 26 Current — Current is not LTS until Oct 2026).
- Locked PostgreSQL to **17.x** (not 18 — 18.0–18.2 had regressions; 18 is fine in 6–12 months).
- Locked PyTorch to **2.11.x** (March 2026 release, well-shaken-out — not 2.12 which is two weeks old).
- Added explicit license notes for **F5-TTS** (CC-BY-NC-4.0) and **XTTS-v2** (CPML) — both compatible with this project's non-commercial educational use case, but the constraint is now documented and we make it impossible to accidentally violate.

---

## 1. Mission

Build a self-hosted web application that turns lecture slides into narrated videos where the narration is in the professor's own voice — synthesized by an AI voice-cloning model from a short reference recording. The professor uploads slides (PDF or PPTX), the system generates a per-slide explanatory script using a multimodal LLM (the LLM sees the actual slide image, not just OCR text), the professor reviews and edits each script, the system synthesizes audio in his voice, and the final MP4 is assembled.

**Why we are building this:** commercial equivalents (ElevenLabs, HeyGen, Synthesia) are paid and proprietary. Our user is a professor who wants a free, open-source alternative his lab can run on their own hardware. This is not a SaaS — it's a tool he installs and owns.

**Use case is strictly non-commercial / educational.** This matters because two of our model dependencies (F5-TTS, XTTS-v2) carry non-commercial licenses. Future commercial use would require swapping those out — which the adapter pattern in §3 makes a config change, not a rewrite.

**Primary user:** one professor, in front of a browser, occasionally producing videos.
**Secondary users:** other faculty / TAs the professor invites later.
**Consumers of the output:** students (passive — they just watch the MP4).

---

## 1.1 Delivery Model — Web App First, Desktop Wrap Later

**Decision: build the web app. Wrap it as a Windows desktop app later, only if needed. One codebase, both ways.**

The deciding factor is where the GPU lives (voice cloning needs one to be usable):
- If the professor has an NVIDIA GPU in his own PC → everything runs locally; his voice never leaves his machine (a real privacy win for biometric voice data); zero hosting cost.
- If the GPU lives on a lab server → a browser-based web app lets multiple faculty share it.

We do not have to choose now, because the stack in this brief (FastAPI + Next.js + Docker) **is already a web app**. To make it a Windows desktop app later, we wrap it with **Tauri** (preferred over Electron — far lighter, modern, Rust-based shell): the desktop window loads our existing frontend, and the backend runs as a bundled local process. We write the app once. The desktop app is a thin shell around the web app we are already building.

**The one behavioral difference is abstracted behind a single config flag from day one:**

| `DEPLOYMENT_MODE` | Final output step behavior |
|---|---|
| `web` (default) | "Download video" button streams the MP4 from object storage to the browser. |
| `desktop` | "Save to folder" uses Tauri's native filesystem access to write the MP4 to a chosen directory — no download round-trip. |

This is **one conditional in the output step**, not two codebases. The frontend reads `DEPLOYMENT_MODE` at build/runtime; everything else is identical. Do not branch the architecture on this — branch exactly one UI behavior. The Tauri packaging is a later, optional task (post Phase 9) and must remain a *packaging* concern, never a refactor. No code written in Phases 1–9 may assume a browser-only or desktop-only environment except the single output-step conditional.

---

## 1.2 Language & Performance Rationale (why Python is correct here)

A reasonable question: should the hot path be C/C++/Rust/Cython instead of Python? **No — and the reasoning matters, so it is recorded here as a binding decision, not a preference.**

Python in this system is the **orchestrator, not the worker**. End-to-end user-facing time is dominated by systems already written in C/C++/CUDA, with Python contributing a rounding error:

| Step | Typical time (30-slide deck) | What actually determines it |
|---|---|---|
| PDF → PNG render | ~5–10 s | PyMuPDF's C core |
| Script generation × N | ~30–60 s | Gemini API network latency (or local Ollama GPU) |
| Voice synthesis × N | ~3–8 min | GPU / CUDA, PyTorch C++ kernels |
| ffmpeg assembly | ~15–30 s | ffmpeg, written in C |
| **Pure-Python glue overhead** | **~0.5–2 s total** | the only part a rewrite would touch |

Rewriting the glue in C++/Rust would save fractions of a percent while discarding the Python ML ecosystem (PyTorch, F5-TTS, Whisper, PyMuPDF) that the entire product depends on. That is a bad trade.

**What actually moves the needle (in priority order) — these are the optimization levers, a language change is not one of them:**
1. **Warm GPU worker** — load the TTS model into VRAM once at worker startup, never per task. Saves 10–15 s *per slide*. Already mandated in §7.3 and Phase 4 acceptance.
2. **Parallel per-slide workers** — `docker compose up --scale worker-gpu=N`. 3–5× throughput. Architecture already supports it via per-slide fan-out.
3. **Better GPU** — RTX 3060 → 4090 is ~4× on synthesis. Hardware, not code.
4. **FP16 / INT8 quantization** of the TTS model — ~2× per-slide inference, minimal quality loss, ~10 lines via native PyTorch. A tracked optimization, not a day-one requirement.
5. **Content-hash caching** — if only 2 of 30 slides changed, re-synthesize only those 2. Enabled by the idempotent task design; implement as a hash check that skips synthesis when `(script_text, voice_profile_id, tts_params)` is unchanged.

**Binding rule:** no one rewrites any component in another language to "make it faster" without first exhausting levers 1–5 and presenting a benchmark in an ADR proving the Python glue is the actual bottleneck. It will not be.

---

## 2. First Principles (Non-Negotiable)


These are the rules. If a decision in this document conflicts with them, the rules win.

1. **This is engineered software, not a prototype.** Every module has a clear responsibility, an interface, and tests. No code lives in a route handler that should live in a service. No service knows about HTTP. No domain logic knows about the database driver.

2. **Pluggable components behind interfaces.** TTS engine, LLM provider, blob storage, and task queue are all swappable. We start with F5-TTS, Gemini, SeaweedFS, Celery+Valkey — but the code must not know or care. If swapping F5-TTS for XTTS-v2 requires changing anything outside `services/tts/`, the abstraction has failed.

3. **Stateless application services.** Any backend container can be killed at any time and another instance picks up the work. State lives in Postgres, Valkey, or object storage — never in process memory or local disk (except as ephemeral scratch space inside a single task).

4. **Long-running work is queued and idempotent.** Slide parsing, script generation, TTS synthesis, and video assembly are all background jobs. Every job can be retried safely. Every job reports progress. Every job is resumable if the worker dies mid-execution.

5. **Configuration via environment, secrets never in code.** Twelve-factor app. A single `.env.example` documents every knob. The code reads through a typed config object — no `os.environ.get` scattered around.

6. **Observability is not optional.** Structured JSON logs with correlation IDs from day one. Every external call (LLM, TTS, storage) is timed and logged. Job status is queryable. We don't add observability "later" — later never comes.

7. **Garbage in → garbage out applies to us too.** Inputs are validated at the boundary. File uploads are sniffed, size-capped, and virus-scoped. LLM outputs are schema-validated before being trusted. We do not pass raw user input or raw model output into downstream systems and hope.

8. **Tests are part of the deliverable.** Service-layer code has unit tests. Critical paths have integration tests. A PR with new logic and no tests is incomplete. Coverage is a smell-check, not a target — but services layer should sit above 80%.

9. **Documentation is part of the deliverable.** Every non-trivial decision gets an ADR in `docs/adr/`. The README explains how to run, test, and deploy. The API is documented via OpenAPI, auto-generated.

10. **No premature optimization, no premature abstraction.** Build the simplest thing that satisfies the principles above. Add layers when a second concrete need appears, not on speculation.

11. **Version discipline.** Every dependency is pinned. Every upgrade is intentional. We do not run `pip install -U`. We do not have a `^` in `package.json` without a `package-lock.json` next to it. Dependabot/Renovate proposes upgrades; humans (and a passing test suite) approve them. See §5 for the compatibility matrix that explains *why* the pins are where they are.

---

## 3. Architecture

### 3.1 Logical view

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│   Next.js   │─────▶│   FastAPI    │─────▶│   PostgreSQL    │
│  Frontend   │ HTTP │   Gateway    │ SQL  │   (metadata)    │
└─────────────┘      └──────┬───────┘      └─────────────────┘
                            │
                            │ enqueue
                            ▼
                     ┌──────────────┐      ┌─────────────────┐
                     │    Valkey    │◀────▶│  Celery Workers │
                     │   (broker)   │      │  (CPU + GPU)    │
                     └──────────────┘      └────────┬────────┘
                                                    │
                            ┌───────────────────────┼──────────────────────┐
                            ▼                       ▼                      ▼
                   ┌────────────────┐     ┌────────────────┐     ┌────────────────┐
                   │ Slide Service  │     │ Script Service │     │  TTS Service   │
                   │  (PyMuPDF,     │     │  (Gemini API   │     │  (F5-TTS /     │
                   │   LibreOffice) │     │   adapter)     │     │   XTTS-v2)     │
                   └────────┬───────┘     └────────┬───────┘     └────────┬───────┘
                            │                     │                       │
                            └─────────────────────┼───────────────────────┘
                                                  ▼
                                       ┌────────────────────┐     ┌────────────────┐
                                       │  Video Assembler   │────▶│   SeaweedFS    │
                                       │     (ffmpeg)       │     │ (S3-compatible)│
                                       └────────────────────┘     └────────────────┘
```

### 3.2 Service boundaries

- **API gateway (`backend/app/api/`)** — thin. Validates requests, enqueues jobs, returns job IDs and status. No business logic.
- **Domain layer (`backend/app/domain/`)** — pure Python, no I/O. Entities (`Project`, `Slide`, `Script`, `AudioClip`, `VideoArtifact`), value objects, domain services.
- **Service layer (`backend/app/services/`)** — orchestrates I/O. One subpackage per capability (`slides/`, `script/`, `tts/`, `video/`, `storage/`). Each exposes a stable interface; implementations are swappable.
- **Task layer (`backend/app/tasks/`)** — Celery tasks. Tasks are thin wrappers that call service layer, handle retries, and update job status. Tasks do not contain business logic.
- **Persistence (`backend/app/db/`)** — SQLAlchemy 2.0 (async). Repositories return domain objects, not ORM models, to the service layer.

### 3.3 Data flow for a single video

1. User creates a `Project` via the API (the dashboard's "Create new lecture video" button does this automatically). A row appears in Postgres.
2. User uploads a slide deck. File goes to SeaweedFS under `projects/{id}/source/`. A `slide_ingestion` job is enqueued. The upload step allows delete + re-upload before continuing.
3. Worker pulls the file, renders each page to PNG, extracts text, persists `Slide` rows pointing at the rendered images in SeaweedFS.
4. **Voice step.** Either the user selects an existing `VoiceProfile` (record-once-reuse-forever; see §3.6) or records a new ~60-second clip. On a *new* recording: the raw audio is stored under `users/{id}/voices/{profile_id}/`, and a `voice_ingestion` job runs **Whisper transcription** on it (§3.5). The transcript is persisted on the `VoiceProfile` as the **style reference**. Immediately after, a **voice preview** job synthesizes one short fixed test sentence so the user can confirm clone quality in seconds before proceeding.
5. User triggers script generation. A `script_generation` job per slide (fan-out) is enqueued. Each job calls the LLM adapter with the slide image, the slide text, **and the active `VoiceProfile`'s style-reference transcript** so generated wording matches the professor's own vocabulary, phrasing, and grammar. The response is validated against a Pydantic schema and persisted as a `Script` row.
6. User reviews scripts in the per-slide editor: switch slide (tabs/dropdown), the editable text box swaps to that slide's script, edit freely, explicit **Save** per slide. Optionally adds pronunciation hints. Regeneration is **per-slide**.
7. User triggers synthesis. A `tts_synthesis` job per slide is enqueued, each using the active `VoiceProfile`. Each writes an audio file to `projects/{id}/audio/` and persists an `AudioClip` row. The audio review step lets the user play each clip and, if unsatisfied, branch back to *change voice* or *change scripts* — which re-runs only the affected slides.
8. User triggers final render. A `video_assembly` job concatenates the ordered `(slide_image, audio_clip)` pairs into a single MP4 via ffmpeg (slide *n* shows for exactly the duration of audio clip *n*, then advances), writes to `projects/{id}/output/`, persists a `VideoArtifact` row.
9. Frontend subscribes via SSE (or polls as fallback) for job status; on completion it auto-advances to the output step. In `web` mode it offers "Download video"; in `desktop` mode it offers "Save to folder" (§1.1). The video is always already persisted to the project, so the user can also retrieve it later.

### 3.4 Why this shape

- **Queue-based** because TTS on GPU takes 5–60 seconds per slide; HTTP requests would time out and we'd need polling anyway.
- **Per-slide fan-out** so a 40-slide deck parallelizes across workers and the user can preview slide-by-slide, edit one slide, and regenerate only that slide without redoing the rest.
- **Object storage from day one** because slide images, audio, and video are blobs and putting them in Postgres or a Docker volume will hurt later.
- **Adapter pattern on TTS/LLM/storage** because the user has explicitly said the project must remain open-source and free — but the best free model today may not be the best in six months. We bet on the interface, not the vendor. The MinIO → SeaweedFS swap forced by Feb 2026 events is the proof: zero application-layer changes.
- **Voice belongs to the user, not the project** so that the second and every subsequent lecture skips recording entirely — upload slides, pick the saved voice, go. This is the single biggest driver of repeat adoption.

### 3.5 The voice recording does double duty

A single ~60-second recording feeds two independent systems, and conflating them is a common and costly mistake:

- **Audio → voice clone (F5-TTS):** captures *how words sound* — timbre, pace, pauses, intonation. This is the TTS reference.
- **Transcript (Whisper) → style reference (LLM):** captures *which words and what phrasing* — vocabulary, sentence structure, grammar, register. This is injected into the script-generation prompt as a style exemplar.

The voice clone alone cannot make the script "sound like him" in word choice — it only controls audio. The transcript closes that gap. Whisper runs locally and free (`faster-whisper`), so no extra API cost. Optionally, the user may also paste/upload a past lecture transcript or notes as an additional/alternative style sample on the `VoiceProfile`.

### 3.6 Core entities (domain model)

- **`User`** — owns voice profiles and projects. (Auth starts as API-key-per-user; §7.4.)
- **`VoiceProfile`** — *user-owned, reusable across projects.* Fields: reference audio (blob key), Whisper transcript (style reference), optional extra style sample, display name, created-at, TTS engine + params used. A user may have several (e.g., "English lecture voice", "casual"). Exactly one is "active" per project at synthesis time.
- **`Project`** — one lecture video effort. References a `VoiceProfile`. Holds the wizard's current state (the step state machine, §8) so the user can leave and resume.
- **`Slide`** — page image (blob key) + extracted text + order index, belongs to a `Project`.
- **`Script`** — editable narration text for one `Slide`, plus estimated reading time and optional pronunciation hints. Versioned-enough to know if it changed since last synthesis (for cache-skip, §1.2 lever 5).
- **`AudioClip`** — synthesized audio (blob key) for one `Script`, with duration and the `(script_hash, voice_profile_id, tts_params)` fingerprint used for idempotent cache-skip.
- **`VideoArtifact`** — the final MP4 (blob key) for a `Project`, plus the SRT subtitle side-artifact and total duration.

The repository layer returns these domain entities, never ORM models, to the service layer (§3.2).

---

## 4. Tech Stack — Locked Versions (May 2026)

Every version below is pinned deliberately. If you want to change one, propose an ADR with the cross-component impact analysis (see §5). Patch-version upgrades inside the same minor are fine via Renovate; minor or major upgrades require an ADR.

### 4.1 Runtime

| Component | Version | Notes |
|---|---|---|
| **Python** | **3.13.x** (latest 3.13.13, Apr 7 2026) | Not 3.14. Celery 5.6 does not yet support 3.14. PyTorch 2.11+ wheels for 3.13 are first-class. |
| **Node.js** | **24 LTS** (latest 24.15+, "Krypton") | Active LTS until April 2028. Not 26 — Current line, not LTS until Oct 2026. |
| **pnpm** | **10.x** | Faster than npm, deterministic, monorepo-friendly. |
| **uv** | **latest** | Replaces pip/pip-tools. Mature, fast, deterministic. |

### 4.2 Backend (Python)

| Component | Version | Notes |
|---|---|---|
| **FastAPI** | **^0.135.0** | Latest is 0.136.3 (May 23 2026), but pinning one minor back gives a stability buffer. Requires Pydantic v2. |
| **Pydantic** | **^2.10** | Latest 2.x. Used for request/response schemas and `pydantic-settings` for config. |
| **SQLAlchemy** | **==2.0.49** | Not 2.1 (still beta, Apr 16 2026). 2.0.49 (Apr 3 2026) is the current stable line. Async via `sqlalchemy[asyncio]`. |
| **Alembic** | **latest 1.x** | Migrations. |
| **asyncpg** | **latest 0.30.x** | Async PostgreSQL driver. Faster than psycopg under async load. |
| **Celery** | **==5.6.3** (Mar 26 2026) | Constrains Python ≤3.13 and redis-py ≤5.2.1. |
| **redis-py** | **==5.2.1** | Pinned by Celery 5.6. Works against both Redis 7.x and Valkey 8.x (wire-compatible). |
| **structlog** | **^25.x** | Structured JSON logging. |
| **OpenTelemetry** | **opentelemetry-distro ^0.50** | API + SDK + auto-instrumentation. |
| **tenacity** | **^9.x** | Retry decorator for external calls. |
| **httpx** | **^0.28** | Async HTTP client + test client. |
| **boto3 / aioboto3** | **latest** | S3-compatible client for SeaweedFS. Works unchanged. |
| **ruff** | **latest** | Lint + format. Replaces black + isort + flake8. |
| **mypy** | **^1.13** | `--strict`. |
| **pytest** | **^8.x** + `pytest-asyncio ^0.25`, `pytest-cov` | |

### 4.3 Frontend (TypeScript)

| Component | Version | Notes |
|---|---|---|
| **Next.js** | **^16.2.0** | Current LTS (16.2.6 latest, May 7 2026). Next.js 15 LTS ends Oct 21 2026. |
| **React** | **^19.x** | Required by Next 16. Server Components by default. |
| **TypeScript** | **^5.7** | `strict: true`, `noUncheckedIndexedAccess: true`. |
| **Tailwind CSS** | **^4.x** | CSS-first config (`@theme` directive). No more `tailwind.config.js` by default. |
| **shadcn/ui** | **Tailwind v4 + React 19 variant** | Fully compatible (Jan 2025 onward). Use `npx shadcn@latest add <component>`. |
| **TanStack Query** | **^5.x** | Server state. |
| **Zod** | **^3.x** | Runtime validation of API responses, mirrors backend Pydantic schemas. |
| **Playwright** | **^1.50** | E2E on critical flows. |

### 4.4 ML / Media

| Component | Version | Notes |
|---|---|---|
| **PyTorch** | **==2.11.0** (Mar 23 2026) | Not 2.12 — two weeks old at time of writing. 2.11 has full Python 3.13 + 3.14 wheels and `torch.compile` Python 3.14 support landed already. |
| **F5-TTS** | **latest from `SWivid/F5-TTS`** | Primary TTS. **License: CC-BY-NC-4.0 (non-commercial only).** Acceptable for our use case; flagged in the LICENSE_AUDIT.md so it cannot be accidentally violated. |
| **coqui-tts** | **^0.27** (idiap community fork on PyPI) | Provides XTTS-v2. The original `TTS` package is archived. **XTTS-v2 license: CPML (non-commercial).** Requires `torch.serialization.add_safe_globals` workaround for PyTorch ≥2.6 — encapsulated in the adapter. |
| **faster-whisper** | **^1.1** | Local, free speech-to-text. Transcribes the voice recording to produce the LLM **style reference** (§3.5). MIT license. Runs on the same GPU worker; `base` or `small` model is plenty for a clean 60s clip. Encapsulated behind a `Transcriber` interface so it's swappable. |
| **Gemini API** | **gemini-2.5-flash** (default), **gemini-3-flash** opt-in via env | Stable, multimodal, generous free tier. Models accessed via `google-genai` SDK ^1.x. |
| **Ollama (optional local LLM)** | **latest** | For users who want zero-API setup. **Default model: `qwen2.5-vl:7b`** (multimodal). Selected via `LLM_PROVIDER=ollama` env. |
| **PyMuPDF** | **^1.24** | PDF parsing + page rendering. License-aware: PyMuPDF is AGPL; if you ever distribute the app you must comply. For self-hosted source release: fine. |
| **LibreOffice** | **25.x** (Docker image `linuxserver/libreoffice` or `collabora/code`) | Headless `soffice --headless --convert-to pdf` for PPTX → PDF. |
| **ffmpeg** | **7.x** (system package, ≥ 7.0) | Subprocess only. No `moviepy`. |

### 4.5 Infrastructure

| Component | Version | Notes |
|---|---|---|
| **PostgreSQL** | **17.x** (latest 17.10, May 14 2026) | Not 18. PG18 is great but had 18.0–18.2 regressions; we will adopt PG18 in a later phase. PG17 is supported through Nov 2029. |
| **Valkey** | **8.x** (replaces Redis) | Linux Foundation BSD-3 fork of Redis 7.2.4. Wire-compatible with Redis (RESP2/RESP3). Works unchanged with `redis-py` and Celery. Image: `valkey/valkey:8-alpine`. |
| **SeaweedFS** | **^3.80** (replaces MinIO) | Apache 2.0, S3-compatible. Single-binary mode for our scale. Image: `chrislusf/seaweedfs:latest` pinned by digest in compose. Adopted by Kubeflow Pipelines as default storage after MinIO's Feb 2026 archive. |
| **Docker** | **^28.x** + **Compose v2** | |
| **Nginx** | **1.27** (stable) | Reverse proxy in prod compose overlay. Or Caddy 2.8 if you prefer auto-TLS. |

### 4.6 Why these versions and not the newest

We are not running the bleeding edge. We are running the **last well-shaken-out minor** in every line that has one. Specifically:

- We did not pick **Python 3.14** because Celery 5.6 (Mar 2026) does not yet list 3.14 support, and our task queue is a load-bearing dependency. Re-evaluate in Q3 2026 when Celery 5.7 (likely 3.14-ready) ships.
- We did not pick **PyTorch 2.12** because it released two weeks before this document (May 13 2026); we want the bug reports from the first month of real production usage to land in 2.12.1+.
- We did not pick **PostgreSQL 18** despite its 3× I/O performance because 18.0 through 18.2 shipped with regressions that required an out-of-cycle release; PG17 is fine for our load (single professor, a few videos a week).
- We did not pick **Next.js 16 latest minor (the very newest patch)** without checking the security release notes — Next.js shipped 13 advisories in May 2026 (CVE-2026-23870 et al.); we pin to a patch that includes those fixes (16.2.6+).
- We did not pick **Node.js 26** because it's the Current line, not LTS. It becomes LTS in Oct 2026.

---

## 5. Compatibility Matrix & Version Rationale

These are the cross-component constraints that determine the pins above. **Any future upgrade must check every row that mentions the changed component.**

### 5.1 Constraints

| If you change → | You must check |
|---|---|
| **Python version** | PyTorch wheels, Celery support, F5-TTS deps (torch + transformers + torchaudio), coqui-tts wheels, asyncpg wheels. PyMuPDF wheels. |
| **PyTorch version** | F5-TTS compat, XTTS-v2 weights loading (`add_safe_globals` API stability), CUDA driver version on GPU host, `torch.compile` regressions. |
| **FastAPI version** | Pydantic v2 minor (FastAPI moves with it), Starlette breaking changes, OpenAPI schema diff (frontend regenerates client). |
| **Celery version** | Python upper bound, redis-py upper bound, kombu deps, Pydantic-arg support. |
| **Next.js version** | React version (lockstep), eslint-config-next, Node.js minimum (Next 16 needs ≥ 18.18; we run 24 LTS so we have headroom). |
| **Tailwind version** | shadcn/ui style variants (v3 vs v4 — different `@theme` config; CSS variables refactored), tailwind-merge, postcss vs vite plugin. |
| **Valkey/Redis version** | redis-py compatibility (8+ works; we pin 5.2.1 anyway for Celery), Celery broker URL scheme, persistence file format if migrating data. |
| **PostgreSQL version** | asyncpg compatibility, Alembic dialect, any extension we use (`pg_trgm`, `uuid-ossp`, etc.). PG18 changed checksum default and uuidv7() exists natively — note for the future migration. |

### 5.2 The triangle that determines Python: Celery × PyTorch × F5-TTS

This is the single tightest constraint in the stack and worth understanding:

- **Celery 5.6.3** classifies its Python support as 3.9–3.13. Running on 3.14 is unsupported.
- **PyTorch 2.11** has 3.13 and 3.14 wheels.
- **F5-TTS** is a research codebase that pins to whatever its `requirements.txt` says — currently torch ≥ 2.1 and Python 3.10+. It works fine on 3.13.

→ Python 3.13 is the only version where all three are simultaneously supported and stable. Lock it.

### 5.3 The licensing constraint

| Component | License | Implication |
|---|---|---|
| **F5-TTS** | CC-BY-NC-4.0 | Non-commercial use only. **This project is non-commercial educational use → compliant.** Document it in LICENSE_AUDIT.md. |
| **XTTS-v2 model weights** | CPML (Coqui Public Model License) | Non-commercial; commercial use requires Coqui sublicense (which is itself in a weird state since the company shut down). For our use case → compliant. |
| **coqui-tts (idiap fork code)** | MPL 2.0 | Permissive enough for our needs. |
| **PyMuPDF** | AGPL-3.0 | Source code of modifications must be made available under AGPL if we distribute. Self-hosted use is fine. Alternative if this ever bites: `pypdfium2` (Apache 2.0). |
| **MinIO Server (replaced)** | AGPL-3.0 | Why we left even before the archive: AGPL is fine for our self-host but the project is now unmaintained. |
| **SeaweedFS** | Apache-2.0 | Clean, no concerns. |
| **Valkey** | BSD-3-Clause | Clean, no concerns. |
| **Redis 7.4+ / Redis 8** | SSPL + RSALv2 (and later AGPL) | Why we left — license uncertainty for downstream redistribution and future cloud-managed offerings. |
| **PostgreSQL** | PostgreSQL License (permissive) | Fine. |
| **FastAPI, Next.js, React, Tailwind, shadcn/ui, SQLAlchemy** | MIT / similar permissive | Fine. |
| **Gemini API** | Google Cloud Platform Terms | API access is free at our tier; output is yours; no copyleft on outputs. |

A `docs/LICENSE_AUDIT.md` is part of Phase 1 deliverables. It is the file Claude Code regenerates whenever a dependency is added. CI fails if `docs/LICENSE_AUDIT.md` is stale relative to `pyproject.toml` and `package.json`.

### 5.4 Upgrade discipline

- **Patch versions** (e.g., `0.135.0 → 0.135.4`): auto-merged by Renovate after CI passes.
- **Minor versions** (e.g., `0.135 → 0.136`): require a one-paragraph PR note + green CI + manual smoke check.
- **Major versions** (e.g., Next 16 → 17, SQLAlchemy 2.0 → 2.1): require an ADR with cross-component impact analysis using the table in §5.1.
- Renovate config is part of Phase 1. The point of the version pins is not to freeze in 2026 forever — it is to make upgrades intentional.

---

## 6. Project Structure

Generate exactly this layout. Empty directories get a `.gitkeep`.

```
lecturevoice/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app factory
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                # Shared dependencies (auth, db session)
│   │   │   ├── v1/
│   │   │   │   ├── projects.py
│   │   │   │   ├── slides.py
│   │   │   │   ├── scripts.py
│   │   │   │   ├── voices.py
│   │   │   │   ├── jobs.py
│   │   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic Settings
│   │   │   ├── logging.py             # structlog setup
│   │   │   ├── security.py            # auth (start with API key, plan for OIDC)
│   │   │   ├── telemetry.py           # OTel setup
│   │   │   └── errors.py              # Exception hierarchy + handlers
│   │   ├── db/
│   │   │   ├── base.py                # Declarative base, naming convention
│   │   │   ├── session.py             # Async engine, session factory
│   │   │   ├── models/                # ORM models
│   │   │   ├── repositories/          # Repository pattern, async
│   │   │   └── migrations/            # Alembic
│   │   ├── domain/
│   │   │   ├── entities.py            # User, VoiceProfile, Project, Slide, Script, AudioClip, VideoArtifact
│   │   │   ├── value_objects.py
│   │   │   └── exceptions.py
│   │   ├── services/
│   │   │   ├── slides/
│   │   │   │   ├── interface.py       # SlideParser protocol
│   │   │   │   ├── pdf_parser.py
│   │   │   │   ├── pptx_parser.py
│   │   │   │   └── factory.py
│   │   │   ├── transcription/
│   │   │   │   ├── interface.py       # Transcriber protocol (voice clip -> style-reference text)
│   │   │   │   ├── whisper_adapter.py # faster-whisper
│   │   │   │   └── factory.py
│   │   │   ├── script/
│   │   │   │   ├── interface.py       # LLMScriptGenerator protocol
│   │   │   │   ├── gemini_adapter.py
│   │   │   │   ├── ollama_adapter.py
│   │   │   │   ├── prompts.py         # Versioned prompt templates (incl. style-reference injection)
│   │   │   │   └── factory.py
│   │   │   ├── tts/
│   │   │   │   ├── interface.py       # TTSEngine protocol
│   │   │   │   ├── f5_adapter.py
│   │   │   │   ├── xtts_adapter.py
│   │   │   │   └── factory.py
│   │   │   ├── video/
│   │   │   │   ├── assembler.py       # ffmpeg orchestration
│   │   │   │   └── probe.py
│   │   │   └── storage/
│   │   │       ├── interface.py       # BlobStore protocol
│   │   │       ├── s3_adapter.py      # Works with SeaweedFS, MinIO, AWS S3, R2
│   │   │       └── factory.py
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   ├── slide_ingestion.py
│   │   │   ├── voice_ingestion.py     # transcribe recording -> style reference
│   │   │   ├── voice_preview.py       # synthesize one test sentence after recording
│   │   │   ├── script_generation.py
│   │   │   ├── tts_synthesis.py
│   │   │   └── video_assembly.py
│   │   └── schemas/                   # Pydantic request/response models
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── pyproject.toml                 # uv-managed, fully pinned
│   ├── uv.lock                        # committed
│   ├── alembic.ini
│   ├── Dockerfile                     # Multi-stage, slim, python:3.13-slim base
│   ├── Dockerfile.gpu                 # nvidia/cuda:12.4-runtime-ubuntu22.04 + python 3.13
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── (dashboard)/                # "Create new lecture video" button -> POST /projects -> redirect into wizard
│   │   ├── projects/[id]/
│   │   │   └── wizard/                 # Single stepper route; step driven by project state machine (§8)
│   │   │       ├── upload/             # Step 1: upload slides (delete + re-upload, then Next)
│   │   │       ├── voice/              # Step 2: pick saved VoiceProfile OR record ~60s; preview clip
│   │   │       ├── scripts/            # Step 3: progress -> per-slide editor (the critical screen)
│   │   │       ├── audio/              # Step 4: progress -> per-slide playback; change-voice/change-scripts
│   │   │       ├── render/             # Step 5: progress while ffmpeg assembles
│   │   │       └── done/               # Step 6: output video; web=Download, desktop=Save-to-folder
│   │   ├── voices/                     # Manage saved VoiceProfiles (rename, delete, set default)
│   │   └── settings/
│   ├── components/
│   │   ├── ui/                        # shadcn primitives
│   │   ├── wizard/                    # Stepper shell + step state machine, back-navigable
│   │   ├── slide-editor/             # Two-pane: slide image | editable script, per-slide save & regenerate
│   │   ├── voice-recorder/          # MediaRecorder capture, level meter, playback, re-record
│   │   ├── voice-preview/           # Plays the one-sentence clone test
│   │   └── job-progress/            # SSE-driven progress bars (one per slide where relevant)
│   ├── lib/
│   │   ├── api-client.ts              # Typed client, generated from OpenAPI
│   │   ├── schemas.ts                 # Zod schemas mirroring backend
│   │   ├── deployment.ts              # reads DEPLOYMENT_MODE (web|desktop); single source for the output-step branch
│   │   └── hooks/
│   ├── tests/
│   ├── package.json
│   ├── pnpm-lock.yaml                 # committed
│   ├── tsconfig.json
│   ├── tailwind.config.ts             # minimal; theme lives in app/globals.css under @theme
│   └── Dockerfile                     # node:24-alpine
├── infra/
│   ├── docker-compose.yml             # Base: API, worker-cpu, postgres, valkey, seaweedfs, frontend
│   ├── docker-compose.gpu.yml         # Overlay: adds worker-gpu
│   ├── docker-compose.prod.yml        # Overlay: adds nginx, healthchecks, restart policies
│   └── nginx/
├── docs/
│   ├── README.md
│   ├── architecture.md
│   ├── api.md
│   ├── runbook.md                     # How to operate this in prod
│   ├── LICENSE_AUDIT.md               # Generated, CI-enforced
│   ├── adr/
│   │   ├── 0001-record-architecture-decisions.md
│   │   ├── 0002-choose-f5-tts-as-primary.md
│   │   ├── 0003-celery-over-arq.md
│   │   ├── 0004-seaweedfs-over-minio.md
│   │   ├── 0005-valkey-over-redis.md
│   │   ├── 0006-python-3-13-pin.md
│   │   ├── 0007-web-first-tauri-desktop-later.md
│   │   ├── 0008-python-as-orchestrator-no-rewrite.md
│   │   ├── 0009-voiceprofile-user-owned-reusable.md
│   │   ├── 0010-recording-double-duty-clone-plus-style.md
│   │   └── ...
│   └── prompts/                       # Versioned LLM prompts as plain markdown
├── scripts/
│   ├── seed.py
│   ├── bench-tts.py                   # Latency / quality benchmarks
│   ├── license-audit.py               # Regenerates docs/LICENSE_AUDIT.md
│   └── load-test.sh
├── .github/
│   └── workflows/
│       ├── backend-ci.yml
│       ├── frontend-ci.yml
│       ├── license-audit.yml          # Fails PR if LICENSE_AUDIT.md is stale
│       └── e2e.yml
├── .gitignore
├── .editorconfig
├── renovate.json                      # Patch auto-merge config
├── Makefile                           # make up / down / test / lint / migrate
└── README.md
```

---

## 7. Non-Functional Requirements

### 7.1 Scalability
- API and workers are stateless. Scaling = `docker compose up --scale worker-gpu=N`.
- Queue-based decoupling means slow TTS does not block the API.
- Per-slide fan-out lets a single video benefit from worker parallelism.
- Object storage is S3-compatible from day one — swapping SeaweedFS for AWS S3 / R2 / Backblaze B2 is an env-var change.
- Database schema uses sensible indexes; N+1 queries are caught in code review.
- The system is K8s-ready (12-factor) without being K8s-coupled. We do not write Helm charts now, but no choice we make today blocks them.

### 7.2 Reliability
- All Celery tasks: `acks_late=True`, `task_reject_on_worker_lost=True`, `max_retries` with exponential backoff via `autoretry_for`, idempotent by design (re-running a task produces the same result, not duplicate side effects).
- External calls (LLM, TTS model HTTP, storage) wrapped with timeout + retry + circuit breaker (`tenacity` for retry; `pybreaker` or in-house breaker for circuit logic).
- Graceful degradation: if the LLM is down, the user can still write scripts manually; if F5-TTS is down, fall back to XTTS-v2 automatically (logged loudly).
- Health checks: `/health/live` (process up) and `/health/ready` (deps reachable) on every service.
- Backups: nightly `pg_dump` script provided; SeaweedFS data backup procedure in the runbook.

### 7.3 Performance
- TTS worker pins the model in GPU VRAM across tasks (warm worker pattern) — do not load the model per task. Same for the Whisper model on the GPU worker.
- **Cache-skip:** before synthesizing a slide, compare the `(script_hash, voice_profile_id, tts_params)` fingerprint against the existing `AudioClip`. If unchanged, skip synthesis. This is what makes "edit one slide, regenerate one slide" cheap (§1.2 lever 5).
- LLM script generation is batched per project where the API supports it.
- Slide rendering is parallelized across CPU cores within a worker.
- ffmpeg uses hardware acceleration if available (`-hwaccel auto`).
- Frontend: server components by default, client components only where interactivity demands; images served via Next.js Image with proper sizing.
- Target: a 30-slide deck → final MP4 in under 10 minutes on a single RTX 3060-class GPU (12 GB VRAM).
- See §1.2 for the binding rule on language/perf: optimize the warm-worker / parallelism / GPU / quantization / cache levers before ever considering a non-Python rewrite.

### 7.4 Security
- File uploads: MIME-sniffed (not trusted by extension), size-capped (50 MB default, configurable), stored under non-executable paths, never served from the upload directory directly.
- No user-supplied paths reach the filesystem or shell. All `subprocess` calls use list args, never `shell=True`.
- Secrets via env, never logged. A log redaction filter scrubs known secret patterns defensively.
- Auth: start with a single API-key-per-user model (sufficient for a self-hosted lab tool). The auth interface in `core/security.py` is abstracted so OIDC / SSO can be added later without rewriting endpoints.
- Rate limiting on the API gateway (`slowapi` or nginx-level).
- CORS configured restrictively; `*` is never the answer.
- Dependencies pinned and scanned (`pip-audit` in backend CI, `pnpm audit` in frontend CI, fails on high-severity).
- License audit (`scripts/license-audit.py`) regenerates `docs/LICENSE_AUDIT.md`; CI fails if it changes mid-PR without commit.

### 7.5 Maintainability
- `mypy --strict` on backend, `tsc --strict` + `noUncheckedIndexedAccess` on frontend. No `Any`, no `as unknown as`. Escape hatches require an inline comment with reasoning.
- Public functions and classes have docstrings explaining the *why*, not the *what*.
- Functions over ~50 lines or with cyclomatic complexity over ~10 get refactored.
- ADRs for every architectural decision worth arguing about.
- Conventional commits; PR template enforces "what / why / how tested".

### 7.6 Observability
- Every request gets an `X-Request-ID`, propagated to logs and downstream calls.
- Every Celery task logs start, end, duration, and outcome.
- Prometheus metrics: request count/latency/error rate on API; queue depth, job duration histograms, success/failure counters on workers.
- OTel traces wire frontend → API → task → external call. Default exporter is stdout in dev; OTLP exporter to any collector in prod.
- A `/jobs/{id}` endpoint returns enough state for the frontend to render a progress UI without polling Celery internals.

### 7.7 Portability & Delivery Mode
- Runs on a developer laptop without GPU (TTS falls back to CPU with a clear warning that it will be slow).
- Runs on a single GPU server (target deployment).
- Ready for a cloud VM or K8s cluster without code changes — only config.
- **Web ↔ desktop is config, not code (§1.1).** A single `DEPLOYMENT_MODE` env/build flag (`web` | `desktop`) controls exactly one behavior: the final output step (browser download vs. Tauri save-to-folder). No Phase 1–9 code may assume browser-only or desktop-only beyond that one conditional. The Tauri wrap is a post-Phase-9 packaging task.
- **Privacy of biometric data:** voice recordings are biometric. In `desktop`/local mode the recording never leaves the professor's machine. In `web`/server mode, document in the runbook where voice data is stored and how to delete it; never log it; never send it to any third party (the voice clone runs locally on our GPU worker, not via an external API).

### 7.8 Version & License Hygiene (new in v2.0)
- Every dependency is pinned (`uv.lock`, `pnpm-lock.yaml` committed). No floating versions in production.
- Renovate proposes upgrades; CI gates them; humans approve.
- `docs/LICENSE_AUDIT.md` is regenerated by `scripts/license-audit.py` and verified by CI.
- License changes (e.g., a dep relicenses to AGPL) must be surfaced by the audit script and trigger an ADR.

---

## 8. Phased Delivery Plan

Execute in order. Do not start phase N+1 until phase N's acceptance criteria are met. At the end of each phase, write a short summary in `docs/progress.md`.

### Phase 0 — Discovery (you do this first, before coding)
Before generating the skeleton:
1. Read this entire brief, including §5 (compatibility matrix).
2. List, in your reply, any ambiguities or decisions you want to confirm. I will answer them.
3. Propose the initial set of ADRs (0001 through ~0010) as one-line summaries.
4. Confirm the development environment expectation (OS, GPU availability, Docker version, exact Python and Node versions installed locally).
5. Verify that the pinned versions in §4 are all actually pullable from PyPI / npm / Docker Hub at the time you begin (one of them may have been yanked).

Only after I respond, proceed to Phase 1.

### Phase 1 — Foundations
**Deliverables:** Project skeleton matching §6. `docker compose up` brings up postgres, valkey, seaweedfs, API (returns `/health/live`), and frontend (returns a landing page with a "Create new lecture video" button). CI runs lint + type-check + unit tests + license audit on backend and frontend. ADRs committed: 0001 (use ADRs), 0004 (SeaweedFS over MinIO), 0005 (Valkey over Redis), 0006 (Python 3.13 pin), 0007 (web-first, Tauri-desktop-later with single `DEPLOYMENT_MODE` flag), 0008 (Python-as-orchestrator / no non-Python rewrite without benchmark), 0009 (VoiceProfile is user-owned and reusable), 0010 (recording does double duty: clone + Whisper style reference). `uv.lock` and `pnpm-lock.yaml` committed.

**Acceptance:**
- `make up` works on a clean machine with only Docker installed.
- `make test` passes (even if tests are mostly placeholders).
- `make lint`, `make typecheck`, `make license-audit` pass cleanly.
- `.env.example` documents every env var the stack reads.
- `docs/LICENSE_AUDIT.md` is generated and lists every dependency's license.

### Phase 2 — Slide Ingestion
**Deliverables:** Upload endpoint accepts PDF or PPTX. PPTX is converted via LibreOffice. Pages are rendered to PNGs and stored in SeaweedFS. Text is extracted and persisted. Job status is queryable.

**Acceptance:**
- Integration test: upload a sample PDF, assert N `Slide` rows exist, N PNGs in SeaweedFS, text content non-empty for at least one slide.
- Same for a sample PPTX.
- Malformed uploads return 4xx, not 5xx.
- Files larger than the configured cap are rejected at the boundary.

### Phase 3 — Voice Profiles & Transcription
**Deliverables:** `VoiceProfile` entity + endpoints (create from upload/recording, list, rename, delete, set default — all user-scoped). `Transcriber` interface + `faster-whisper` adapter. `voice_ingestion` task: store recording in SeaweedFS, transcribe to a style-reference transcript, persist on the profile. The voice recording belongs to the **user**, reusable across all projects.

**Acceptance:**
- A recorded/uploaded clip produces a `VoiceProfile` with a non-empty transcript.
- A second project can select an existing profile without re-recording (the adoption-critical path — explicitly tested).
- Transcriber has a fake implementation for unit tests; the real model is exercised only in an integration test.
- Deleting a profile removes its blob from storage and is blocked (or soft-handled) if a project still references it.
- Whisper model is loaded once per worker, not per task.

### Phase 4 — Script Generation (style-aware)
**Deliverables:** `LLMScriptGenerator` interface and Gemini adapter using `google-genai` SDK with `gemini-2.5-flash`. Prompts versioned in `docs/prompts/`. Per-slide `script_generation` job. The prompt **injects the active `VoiceProfile`'s style-reference transcript** so generated wording matches the professor's vocabulary, phrasing, and grammar — not just generic explanation. Output validated against a Pydantic schema (script text, estimated reading time, optional pronunciation hints).

**Acceptance:**
- Given a slide (image + text) and a style reference, the adapter returns a script that explains rather than reads, and whose register/phrasing visibly reflects the style sample (verified on a fixture with a distinctive sample).
- A malformed LLM response triggers a single retry with a stricter prompt, then surfaces a clear error.
- Adapter has a fake implementation for tests; unit tests do not call the real API.
- An `LLM_PROVIDER=ollama` config swaps to the local multimodal adapter without code changes.

### Phase 5 — TTS Engine & Voice Preview
**Deliverables:** `TTSEngine` interface, F5-TTS adapter, XTTS-v2 fallback adapter (via `coqui-tts`, with the `torch.serialization.add_safe_globals` workaround encapsulated). `voice_preview` task: synthesize one short fixed test sentence right after recording. Per-slide `tts_synthesis` job with cache-skip on the `(script_hash, voice_profile_id, tts_params)` fingerprint. Audio stored in SeaweedFS. GPU worker keeps model warm.

**Acceptance:**
- Given a ~10s reference clip and a ~30s script, F5 adapter produces a wav in the reference voice in under 30s on a 3060-class GPU.
- The voice-preview test sentence is synthesized and returned quickly enough to confirm clone quality before full generation.
- Cache-skip: re-running synthesis for an unchanged slide does not re-invoke the model (verified via metric/log).
- Model is loaded once per worker process, not per task (verified via startup log line and a metric).
- `scripts/bench-tts.py` reports cold-start, warm latency, and an audio-similarity score against the reference for each adapter.
- Falling back from F5 to XTTS-v2 on failure is automatic and logged.

### Phase 6 — Video Assembly
**Deliverables:** `video_assembly` task takes the ordered (slide PNG, audio wav) pairs and produces an MP4 via ffmpeg subprocess — slide *n* displayed for exactly the duration of audio clip *n*, then advance. Output streamed to SeaweedFS. SRT subtitle side-artifact from script text + audio durations.

**Acceptance:**
- A 5-slide test project produces a playable MP4 with correct duration (≈ sum of audio durations) and correct slide-to-audio alignment.
- Re-running the task overwrites cleanly (idempotent).
- ffmpeg failure is captured with stderr in the job error.
- SRT timing matches audio within ±0.5s.

### Phase 7 — Frontend: Wizard (back-navigable stepper)
**Deliverables:** The full flow as a **stepper backed by a state machine** persisted on the `Project` (so the user can leave and resume), **not** destroy-and-replace DOM. Dashboard "Create new lecture video" button → auto-creates a project → enters the wizard. Steps: **Upload** (single section; delete + re-upload; Next) → **Voice** (pick saved profile or record ~60s; play back; re-record; preview the one-sentence clone) → **Scripts** (per-slide progress, then editor) → **Audio** (per-slide progress, then playback + change-voice/change-scripts) → **Render** (progress) → **Done** (output video). Each long step shows SSE-driven progress (per-slide bars where relevant). The user can step **back** at any point; doing so never discards completed work for unaffected slides. shadcn/ui (Tailwind v4 variant) throughout.

**Acceptance:**
- Playwright test walks the full happy path end-to-end against the real backend in CI, including selecting a previously-saved voice profile on a second project.
- Stepping back from Audio → Scripts, editing slide 7, and continuing regenerates only slide 7's audio (others are cache-skipped).
- Leaving mid-wizard and returning resumes at the same step with state intact.
- Errors are surfaced in plain language, not stack traces. Mobile/tablet-reviewable.

### Phase 8 — Frontend: Per-Slide Script Editor (the critical screen)
**Deliverables:** Two-pane editor inside the Scripts step. Left: slide image with zoom and prev/next and a slide switcher (tabs or dropdown). Right: a large editable text box that swaps to the selected slide's script, an explicit per-slide **Save** button, pronunciation-hints field, "regenerate this slide" button, and "preview audio (this slide only)" that synthesizes just the current slide and plays it inline.

**Acceptance:**
- Switching slides swaps the editor text to that slide's script.
- Editing a script and clicking preview plays the new audio within seconds (warm worker).
- Switching slides preserves unsaved edits within the session; explicit Save persists.
- Long scripts scroll without breaking layout.
- Accessibility: keyboard navigable, ARIA roles correct, contrast WCAG AA.

### Phase 9 — Observability & Hardening
**Deliverables:** Structured logging with correlation IDs end-to-end. OTel traces. Prometheus metrics. Rate limiting. Error handler hierarchy. Backup script. Runbook in `docs/runbook.md`.

**Acceptance:**
- A single request traces frontend → API → task → external call by one ID.
- `/metrics` exposes queue depth and task duration histograms.
- Chaos test (kill a worker mid-task) recovers without data loss.
- Runbook covers: add a user, rotate credentials, restore from backup, scale workers, swap LLM provider, swap TTS provider, **delete a user's voice data**.

### Phase 10 — Polish & Release (web)
**Deliverables:** README aimed at the professor (not engineers). One-command install. Sample voice reference and sample slide deck. CHANGELOG. Versioned Docker images. Output step honors `DEPLOYMENT_MODE=web` (Download button). License for our own code (MIT or Apache-2.0 — propose in an ADR).

**Acceptance:**
- A non-engineer follows the README and has a working web install in under 30 minutes on a fresh machine.

### Phase 11 (optional, post-release) — Desktop Wrap (Tauri)
**Deliverables:** Package the existing frontend + bundled backend as a Windows desktop app via Tauri. Output step honors `DEPLOYMENT_MODE=desktop` (Save-to-folder via native filesystem access). No application logic changes beyond the single output-step branch and packaging glue.

**Acceptance:**
- The same frontend codebase runs unchanged inside the Tauri shell.
- "Save to folder" writes the MP4 to a user-chosen directory with no browser download.
- A diff of `frontend/app` and `frontend/components` between Phase 10 and Phase 11 shows no architectural changes — only the deployment-mode branch and packaging files. If the diff is larger, the abstraction in §1.1 was violated; fix that, don't paper over it.

---

## 9. Working Agreement (How You Work)

1. **Plan before you code.** For any non-trivial change, post the plan in the chat first: files to be touched, new modules, public interfaces, test approach. Wait for confirmation on the first plan of each phase.

2. **Small, reviewable commits.** Each commit does one thing. Conventional Commits.

3. **Tests with the code, not after.** New service method → new tests in the same PR. Found a bug → regression test first, then fix.

4. **Update docs in the same change.** API change → OpenAPI updated. Architecture change → ADR. Operational change → runbook. New dependency → `docs/LICENSE_AUDIT.md` re-checked.

5. **No silent failures.** Every `except` either handles the error meaningfully or re-raises a domain exception with context. No bare `except:`. No `except Exception: pass`.

6. **Boundaries are sacred.** Domain layer imports nothing from `services/`, `db/`, or `api/`. Service layer imports from `domain/` and other services through their interfaces, never their implementations. The dependency graph points inward.

7. **When in doubt, ask.** If a requirement is ambiguous, ask. If a library choice feels wrong, push back. If you can see a better path, propose it as an ADR.

8. **Read before you write.** Before editing any file with significant existing logic, view it. Before adding a dependency, check what we already have and check its license.

9. **When a tool exists, use it.** We have `ruff`, `mypy`, `pytest`, `alembic`, Make targets, the license-audit script. Use them. Don't hand-roll alternatives.

10. **Stop and surface trade-offs.** If implementing a requirement cleanly would take significantly longer than a quick-and-dirty version, stop and present both options with your recommendation. Do not silently take the shortcut.

11. **Never bump a dependency mid-feature.** If a feature needs a newer version of something, that's a separate PR with an ADR if the bump crosses a minor or major boundary.

---

## 10. Anti-Patterns — Things You Must Not Do

- ❌ Business logic in FastAPI route handlers.
- ❌ Raw SQL strings outside the repository layer.
- ❌ `subprocess.run(..., shell=True)` with any string that came from a user.
- ❌ Loading ML models inside a Celery task body (load once at worker startup).
- ❌ Catching `Exception` without re-raising or logging with context.
- ❌ Hardcoding paths, URLs, model names, or magic numbers. They go in config.
- ❌ Skipping tests "because it's just a wrapper".
- ❌ Storing files on a Docker volume that isn't backed by SeaweedFS or Postgres.
- ❌ Writing prompts inline in code. Prompts live in `docs/prompts/` and are loaded by name + version.
- ❌ Adding a new dependency without checking it isn't redundant with one we have, and without re-running the license audit.
- ❌ Touching `main` branch directly. Every change goes through a PR.
- ❌ Saying "for now" or "TODO" without an issue link.
- ❌ Pinning to `latest`, `next`, or `canary`. Every version is an exact number or a tight range.
- ❌ Reaching for the newest minor of any dep without checking the constraint table in §5.1.
- ❌ Branching the architecture on web-vs-desktop. The only allowed difference is the single output-step `DEPLOYMENT_MODE` conditional (§1.1). Anything more means the abstraction failed.
- ❌ Rewriting a component in another language "for speed" before exhausting the §1.2 levers and proving with a benchmark that Python glue is the bottleneck (it won't be).
- ❌ Tying the voice recording to a single project. `VoiceProfile` is user-owned and reused across projects (§3.6).
- ❌ Feeding the script generator only the slide. The active profile's style-reference transcript is part of the prompt (§3.5).
- ❌ Regenerating all slides when one changed. Synthesis is per-slide with cache-skip (§7.3).
- ❌ Logging, exporting, or sending voice recordings anywhere. Biometric data stays local (§7.7).
- ❌ Vibe coding. You are an engineer. Act like one.

---

## 11. Definition of Done (per change)

- [ ] Plan was posted and acknowledged (for non-trivial changes).
- [ ] Code compiles, types check (`mypy --strict`, `tsc --strict`), lints clean (`ruff`, `eslint`).
- [ ] Tests added or updated. Existing tests pass.
- [ ] Docs updated (README / ADR / OpenAPI / runbook / LICENSE_AUDIT as relevant).
- [ ] If a dependency was added or bumped: `uv.lock` / `pnpm-lock.yaml` regenerated, `LICENSE_AUDIT.md` regenerated, §5.1 cross-checks done.
- [ ] No new TODOs without tracked issues.
- [ ] Manual smoke check via `make up` passed if behavior is user-visible.
- [ ] Commit messages are Conventional Commits.

---

## 12. Starting Instruction

Begin with Phase 0. Read this brief end-to-end, including the compatibility matrix in §5. Then, in your first reply, give me:

1. Questions or ambiguities you want resolved before scaffolding.
2. Your proposed initial ADR list (titles only, ~10 ADRs).
3. Any substantive concerns or disagreements — particularly with the version pins in §4 or the rationale in §5. If you think a pin is wrong, say so and propose the alternative with reasoning based on the constraint table.
4. The environment assumptions you're making (Docker version, OS, GPU availability, exact Python and Node versions installed locally, ffmpeg version).
5. Confirmation that you have access to pull the pinned versions of every component in §4 (a one-line `pip index versions <pkg>` / `npm view <pkg> versions` check is enough).

Do not generate code in your first reply. Code starts after I answer your Phase 0 questions.

— End of brief —
