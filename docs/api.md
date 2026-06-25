# API Reference

Auto-generated from OpenAPI spec. With the stack running, see:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Authentication

All endpoints require `X-API-Key: <your-key>` header.

## Phase 1 Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health/live` | Liveness check (no auth required) |
| GET | `/api/v1/health/ready` | Readiness check (checks postgres) |
| GET | `/api/v1/projects` | List projects (stub) |
| POST | `/api/v1/projects` | Create project (stub) |
| GET | `/api/v1/voices` | List voice profiles (stub) |
| GET | `/api/v1/jobs/{job_id}` | Job status (stub) |

Full endpoint documentation added phase by phase.
