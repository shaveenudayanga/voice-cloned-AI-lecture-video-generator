# Runbook — LectureVoice

Operational procedures for running LectureVoice in production.

## Docker Desktop Setup (WSL2)

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
# Edit backend/.env — at minimum set: API_KEY

# 3. Start all services
make up

# 4. Verify
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/health/live
# → {"status":"ok","version":"0.1.0"}
```

## Common Operations

### Scale GPU workers
```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.gpu.yml up --scale worker-gpu=2 -d
```

### Run database migrations
```bash
make migrate
```

### View logs
```bash
make logs
# Or for a specific service:
docker compose -f infra/docker-compose.yml logs -f api
```

### Rotate the API key
1. Generate a new key: `openssl rand -hex 32`
2. Update `API_KEY` in `backend/.env`
3. Restart the API: `docker compose -f infra/docker-compose.yml restart api`
4. Update your client to use the new key

### Add a user (Phase 2+)
Phase 1 uses a single server-wide API key. Per-user keys are added in Phase 2 per `core/security.py TODO(auth-upgrade)`.

### Swap the LLM provider
```bash
# In backend/.env:
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-vl:7b
# Then restart workers:
docker compose -f infra/docker-compose.yml restart worker-cpu
```

### Swap the TTS engine
```bash
# In backend/.env:
TTS_ENGINE=xtts  # or f5
# Restart GPU worker (model is warm-loaded at startup):
docker compose -f infra/docker-compose.gpu.yml restart worker-gpu
```

### Delete a user's voice data
Voice recordings are biometric. To delete a VoiceProfile and its audio:
1. Call `DELETE /api/v1/voices/{profile_id}` — removes DB row and SeaweedFS blob
2. Verify the blob is gone: check SeaweedFS at `STORAGE_ENDPOINT_URL`
3. Log the deletion for your records (GDPR/privacy audit trail)

### Backup

**PostgreSQL:**
```bash
docker compose -f infra/docker-compose.yml exec postgres \
  pg_dump -U lecturevoice lecturevoice > backup_$(date +%Y%m%d).sql
```

**SeaweedFS:** Copy the `seaweedfs_data` Docker volume to a backup location. For production, configure SeaweedFS replication or use a cloud S3-compatible backend (`STORAGE_ENDPOINT_URL=https://...`).

### Restore from backup
```bash
docker compose -f infra/docker-compose.yml exec -T postgres \
  psql -U lecturevoice lecturevoice < backup_20260625.sql
```

## Environment Variables

See `backend/.env.example` for the full list with descriptions.

## Low-VRAM Devices (RTX 3050 Ti / 4 GB)

Set in `backend/.env`:
```
VRAM_BUDGET_GB=4.0
WHISPER_MODEL_SIZE=base
```

The GPU worker will load F5-TTS and Whisper alternately (not simultaneously) when VRAM budget is below 8 GB. Voice preview synthesis may fall back to CPU — expect ~2-4× slower synthesis but correct output.
