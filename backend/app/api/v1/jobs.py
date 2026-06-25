# SPDX-License-Identifier: Apache-2.0
import uuid
from typing import cast

from fastapi import APIRouter, HTTPException

from app.api.deps import AuthDep, SessionDep
from app.db.repositories.job_repository import JobRepository
from app.schemas import JobResponse, JobStatus

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, auth: AuthDep, session: SessionDep) -> JobResponse:
    """Return current status of a background job."""
    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid job_id") from None

    repo = JobRepository(session)
    job = await repo.get(jid)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Map internal status vocabulary to public API vocabulary
    status_map = {
        "queued": "queued",
        "pending": "queued",
        "running": "running",
        "success": "complete",
        "complete": "complete",
        "failed": "failed",
        "retrying": "running",
    }
    public_status = status_map.get(job.status, "queued")

    return JobResponse(
        job_id=job.id,
        status=cast(JobStatus, public_status),
        progress_pct=job.progress_pct,
        error_message=job.error_message,
        result=job.result_payload,
    )
