# Architecture — LectureVoice

See `PROJECT_BRIEF.md §3` for the full architecture narrative. This document is the living reference — updated as phases complete.

## Service Topology

```
Next.js Frontend  →  FastAPI Gateway  →  PostgreSQL 17
                            │
                            │  enqueue (Valkey 8)
                            ▼
                      Celery Workers ──→ SeaweedFS (S3-compatible)
                      (CPU + GPU)
                            │
                    ┌───────┼───────┐
                    ▼       ▼       ▼
               Slides  Scripts   TTS
             (PyMuPDF) (Gemini) (F5-TTS)
                              └──▶ Video Assembly (ffmpeg)
```

## Key Design Decisions

See [adr/](adr/) for the full rationale. Quick reference:

| Decision | ADR |
|---|---|
| SeaweedFS replaces MinIO | ADR-0004 |
| Valkey replaces Redis | ADR-0005 |
| Python 3.13 pin | ADR-0006 |
| Web-first, Tauri later | ADR-0007 |
| Python as orchestrator | ADR-0008 |
| VoiceProfile is user-owned | ADR-0009 |
| Recording does double duty | ADR-0010 |

## Service Boundaries

- **API (`backend/app/api/`)** — thin; validates, enqueues, returns job IDs
- **Domain (`backend/app/domain/`)** — pure Python; no I/O
- **Services (`backend/app/services/`)** — one subpackage per capability; pluggable via Protocol interfaces
- **Tasks (`backend/app/tasks/`)** — Celery tasks; thin wrappers over services
- **DB (`backend/app/db/`)** — SQLAlchemy 2.0 async; repositories return domain entities

## Data Flow (30-slide deck, happy path)

1. Upload PDF/PPTX → `slide_ingestion` task → N Slide rows + PNGs in SeaweedFS
2. Select/record VoiceProfile → `voice_ingestion` → Whisper transcript → style reference
3. Voice preview → `voice_preview` → one synthesized sentence → user confirms clone quality
4. Generate scripts → N × `script_generation` tasks (fan-out) → N Script rows
5. User reviews/edits scripts per-slide; regeneration is per-slide with cache-skip
6. Synthesize audio → N × `tts_synthesis` tasks → N AudioClip rows
7. Assemble video → `video_assembly` → single MP4 + SRT in SeaweedFS
8. Output step → `web`: browser download | `desktop`: Tauri save-to-folder
