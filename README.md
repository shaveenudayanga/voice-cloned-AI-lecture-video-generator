# LectureVoice

Turn lecture slides into narrated videos in the professor's own voice. Self-hosted, open-source, free.

**License:** Apache-2.0 | **Model dependencies:** F5-TTS (CC-BY-NC-4.0), XTTS-v2 (CPML) — non-commercial educational use only

---

## Quick Start

**Requirements:** Docker Desktop, 8 GB RAM minimum (16 GB recommended), NVIDIA GPU for production use.

```bash
# 1. Clone
git clone <repo-url>
cd voice-cloned-AI-lecture-video-generator

# 2. Configure
cp backend/.env.example backend/.env
# Edit backend/.env — set API_KEY at minimum

# 3. Start
make up

# 4. Open
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
```

## Make Targets

| Command | Description |
|---|---|
| `make up` | Start all services |
| `make down` | Stop all services |
| `make up-gpu` | Start with GPU worker |
| `make test` | Run unit tests |
| `make lint` | Run ruff + ESLint |
| `make typecheck` | Run mypy + tsc |
| `make migrate` | Run DB migrations |
| `make license-audit` | Regenerate LICENSE_AUDIT.md |
| `make check-env` | Verify local environment |

## Architecture

See [docs/architecture.md](docs/architecture.md) and [PROJECT_BRIEF.md](PROJECT_BRIEF.md).

## Low-VRAM Setup (RTX 3050 Ti / 4 GB)

```bash
# In backend/.env:
VRAM_BUDGET_GB=4.0
WHISPER_MODEL_SIZE=base
```

## License Note

This project's source is Apache-2.0. The F5-TTS and XTTS-v2 model weights are **non-commercial only** (CC-BY-NC-4.0 and CPML respectively). See [docs/LICENSE_AUDIT.md](docs/LICENSE_AUDIT.md).
