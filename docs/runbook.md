# Runbook — LectureVoice

Operational procedures for running LectureVoice in production.

---

## Docker / Prerequisites

This project runs on Docker. On WSL2 (Windows):
1. Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
2. In Docker Desktop Settings → Resources → WSL Integration, enable your WSL2 distro
3. Verify in WSL2: `docker info` should succeed

## First-time Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd voice-cloned-AI-lecture-video-generator

# 2. Copy and fill in the env file
cp backend/.env.example backend/.env
# Edit backend/.env — at minimum set: API_KEY, DATABASE_URL, GEMINI_API_KEY

# 3. Start all services
make up

# 4. Verify
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/health/live
# → {"status":"ok","version":"0.1.0"}
```

---

## 1. How to Add a User

Phase 1 uses a single server-wide API key defined by `API_KEY` in `backend/.env`.
All professors who have this key can use the system.

**To add a faculty member:**
1. Share the current `API_KEY` value with them, or generate a new one:
   ```bash
   openssl rand -hex 32
   ```
2. Update `API_KEY` in `backend/.env` if rotating.
3. Restart the API container:
   ```bash
   docker compose -f infra/docker-compose.yml restart api
   ```

> Per-user keys with DB-backed lookup are wired behind `TODO(auth-upgrade)` in
> `backend/app/core/security.py` — the interface is already abstracted.

---

## 2. How to Rotate Credentials

### API Key

1. Generate a new key: `openssl rand -hex 32`
2. Update `API_KEY` in `backend/.env`
3. Restart: `docker compose -f infra/docker-compose.yml restart api`
4. Distribute the new key to all faculty.

### Gemini API Key

1. Revoke the old key in [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Create a new key and update `GEMINI_API_KEY` in `backend/.env`.
3. Restart: `docker compose -f infra/docker-compose.yml restart api worker-cpu`

### SeaweedFS Credentials

1. Update `STORAGE_ACCESS_KEY` and `STORAGE_SECRET_KEY` in `backend/.env`.
2. Update the matching credentials in your SeaweedFS configuration or compose override.
3. Restart: `docker compose -f infra/docker-compose.yml restart api worker-cpu worker-gpu`

---

## 3. How to Restore from Backup

### PostgreSQL

```bash
# Restore from a gzip dump created by scripts/backup.sh
gunzip -c backups/postgres_20260625_120000.sql.gz \
  | docker compose -f infra/docker-compose.yml exec -T postgres \
      psql -U lecturevoice lecturevoice
```

Verify row counts after restore:
```bash
docker compose -f infra/docker-compose.yml exec postgres \
  psql -U lecturevoice lecturevoice -c "\dt"
```

### SeaweedFS

See §8 below for the SeaweedFS volume backup and restore procedure.

---

## 4. How to Scale Workers

### CPU Workers (slide ingestion, transcription, script generation, video assembly)

```bash
docker compose -f infra/docker-compose.yml up --scale worker-cpu=N -d
```

### GPU Workers (TTS synthesis, voice preview)

```bash
docker compose \
  -f infra/docker-compose.yml \
  -f infra/docker-compose.gpu.yml \
  up --scale worker-gpu=N -d
```

Replace `N` with the desired replica count. Each GPU worker holds the TTS model in VRAM
(warm worker pattern — §7.3). With `N` GPU workers and a 30-slide deck, synthesis
parallelizes across workers: a 3060-class GPU running 3 workers completes in roughly
⅓ the single-worker time.

---

## 5. How to Swap the LLM Provider

Current options: `gemini` (default) | `ollama`

```bash
# In backend/.env:
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-vl:7b

# Restart CPU workers (they hold the LLM client):
docker compose -f infra/docker-compose.yml restart worker-cpu
```

To revert to Gemini:
```bash
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
```

No code changes required — the adapter is swapped purely by config.

---

## 6. How to Swap the TTS Engine

Current options: `f5` (default) | `xtts`

```bash
# In backend/.env:
TTS_ENGINE=xtts

# Restart GPU workers (model is loaded at startup, not per task):
docker compose -f infra/docker-compose.gpu.yml restart worker-gpu
```

To revert to F5-TTS:
```bash
TTS_ENGINE=f5
```

The XTTS-v2 adapter includes the `torch.serialization.add_safe_globals` workaround
for PyTorch ≥2.6 — this is encapsulated in `backend/app/services/tts/xtts_adapter.py`.

---

## 7. How to Delete a User's Voice Data

Voice recordings are biometric data. Deletion must be permanent and auditable.

**Option A — API (preferred)**

```bash
curl -X DELETE http://localhost:8000/api/v1/voices/{profile_id} \
  -H "X-API-Key: your-key"
```

This removes the DB row **and** the SeaweedFS blob in one atomic operation.
Returns `204 No Content` on success. Returns `409 Conflict` if any project still
references the profile — detach those projects first by updating their `voice_profile_id`.

**Option B — Manual (if API is unavailable)**

```sql
-- 1. Find the blob key
SELECT id, audio_blob_bucket, audio_blob_key FROM voice_profiles WHERE id = '<profile_id>';

-- 2. Delete from DB
DELETE FROM voice_profiles WHERE id = '<profile_id>';
```

Then delete the blob from SeaweedFS:
```bash
# Using the S3-compatible API:
aws s3 rm s3://lecturevoice/<blob_key> \
  --endpoint-url http://localhost:8333 \
  --no-sign-request
```

**Log the deletion** (timestamp, profile_id, blob_key) for your GDPR/privacy audit trail.
Never log the audio content itself.

---

## 8. SeaweedFS Volume Backup Procedure

SeaweedFS does not have a `pg_dump` equivalent — it is a filesystem-based blob store.
Back it up by archiving the Docker volume contents.

### Create a backup

```bash
# Find the SeaweedFS container name
CONTAINER=$(docker compose -f infra/docker-compose.yml ps -q seaweedfs)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

docker run --rm \
  --volumes-from "$CONTAINER" \
  -v "$(pwd)/backups:/backup" \
  alpine \
  tar czf "/backup/seaweedfs_${TIMESTAMP}.tar.gz" /data

# Verify the archive is non-empty
ls -lh "backups/seaweedfs_${TIMESTAMP}.tar.gz"
```

Stopping write traffic before the snapshot is safer but not strictly required for
a small single-professor deployment (re-synthesis of any partially-written blob is
idempotent).

### Restore from a SeaweedFS backup

```bash
CONTAINER=$(docker compose -f infra/docker-compose.yml ps -q seaweedfs)

docker run --rm \
  --volumes-from "$CONTAINER" \
  -v "$(pwd)/backups:/backup" \
  alpine \
  tar xzf /backup/seaweedfs_<TIMESTAMP>.tar.gz -C /
```

Restart SeaweedFS after restore:
```bash
docker compose -f infra/docker-compose.yml restart seaweedfs
```

---

## 9. How to Check Prometheus Metrics

The `/metrics` endpoint requires no authentication (standard Prometheus convention).

```bash
# Raw text format
curl -s http://localhost:8000/metrics | head -40

# Filter for specific metrics
curl -s http://localhost:8000/metrics | grep http_requests_total
curl -s http://localhost:8000/metrics | grep celery_task_duration
curl -s http://localhost:8000/metrics | grep tts_synthesis_cache

# Pretty-print with column alignment
curl -s http://localhost:8000/metrics | grep -v "^#" | column -t
```

Key metrics to monitor:

| Metric | What it tells you |
|---|---|
| `http_requests_total{status_code="5xx"}` | Server errors — investigate immediately |
| `celery_task_duration_seconds{task_name="tts_synthesis"}` | TTS latency per slide |
| `celery_queue_depth{queue_name="gpu"}` | GPU queue backlog |
| `tts_synthesis_cache_hits_total` / `_misses_total` | Cache efficiency |
| `llm_script_generation_total{status="failure"}` | LLM call failures |

---

## 10. How to Read Structured Logs

All logs are emitted as JSON via structlog. The `request_id` field flows from
the HTTP request through to Celery tasks.

### Basic jq filters

```bash
# Stream logs (API container)
docker compose -f infra/docker-compose.yml logs -f api | jq '.'

# Filter by log level
docker compose -f infra/docker-compose.yml logs api \
  | jq 'select(.level == "error")'

# Follow a specific request end-to-end by its ID
docker compose -f infra/docker-compose.yml logs api worker-cpu worker-gpu \
  | jq 'select(.request_id == "550e8400-e29b-41d4-a716-446655440000")'

# Show only event, level, and request_id (compact view)
docker compose -f infra/docker-compose.yml logs api \
  | jq '{ts: .timestamp, lvl: .level, rid: .request_id, ev: .event}'

# Count errors by event name (last 1000 lines)
docker compose -f infra/docker-compose.yml logs --tail=1000 api \
  | jq 'select(.level == "error") | .event' \
  | sort | uniq -c | sort -rn

# Show all task completions with duration
docker compose -f infra/docker-compose.yml logs worker-gpu \
  | jq 'select(.event == "task_finished") | {task: .task_name, status: .status}'
```

### Correlation ID tracing

Every HTTP request generates a unique `request_id` (UUID4) from `CorrelationIDMiddleware`.
The same ID is passed in the Celery task header and set in the worker's ContextVar
by `task_prerun`, so every log line in both the API and the worker process carries it.

To trace a full request:
1. Note the `X-Request-ID` response header from any API call.
2. Search all container logs: `jq 'select(.request_id == "<id>")'`

---

## Environment Variables

See `backend/.env.example` for the full list with descriptions.

## Low-VRAM Devices (RTX 3050 Ti / 4 GB)

```bash
# In backend/.env:
VRAM_BUDGET_GB=4.0
WHISPER_MODEL_SIZE=base
```

The GPU worker loads F5-TTS and Whisper alternately when VRAM budget is below 8 GB.
Voice preview synthesis may fall back to CPU — expect ~2–4× slower synthesis but
correct output. See §1.2 of the project brief for the full optimization lever priority list.

## Run database migrations

```bash
make migrate
```

## View logs (short form)

```bash
make logs
# Or for a specific service:
docker compose -f infra/docker-compose.yml logs -f api
```
