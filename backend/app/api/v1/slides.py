# SPDX-License-Identifier: Apache-2.0
import uuid

import structlog
from fastapi import APIRouter, HTTPException, UploadFile

from app.api.deps import AuthDep, SessionDep
from app.core.config import settings
from app.db.repositories.job_repository import JobRepository
from app.db.repositories.slide_repository import SlideRepository
from app.schemas import SlideUploadResponse
from app.services.slides.mime import sniff_mime
from app.services.storage.factory import get_blob_store
from app.tasks.slide_ingestion import ingest_slides

router = APIRouter()
logger = structlog.get_logger(__name__)

# Number of bytes to read for magic-byte detection
_MIME_SNIFF_BYTES = 8


@router.get("/projects/{project_id}/slides")
async def list_slides(project_id: str, auth: AuthDep, session: SessionDep) -> dict[str, object]:
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid project_id") from None
    repo = SlideRepository(session)
    slides = await repo.list_by_project(pid)
    return {
        "slides": [
            {
                "id": str(s.id),
                "order_index": s.order_index,
                "extracted_text": s.extracted_text,
            }
            for s in slides
        ]
    }


@router.post("/projects/{project_id}/slides/upload", status_code=202, response_model=SlideUploadResponse)
async def upload_slides(
    project_id: str,
    file: UploadFile,
    auth: AuthDep,
    session: SessionDep,
) -> SlideUploadResponse:
    """Accept a PDF or PPTX upload, store to object storage, enqueue ingestion."""
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid project_id") from None

    # --- Size check (stream header + body in one pass) ---
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_bytes} bytes",
        )

    # --- MIME sniff (do not trust extension or Content-Type alone) ---
    declared = file.content_type or ""
    mime = sniff_mime(raw[:_MIME_SNIFF_BYTES], declared)
    if mime is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a PDF or PPTX file.",
        )

    # --- Store raw file to SeaweedFS ---
    safe_filename = (file.filename or "upload").replace("/", "_").replace("..", "_")
    blob_key = f"projects/{pid}/source/{safe_filename}"
    store = get_blob_store()
    await store.ensure_bucket(settings.storage_bucket)
    await store.put(
        bucket=settings.storage_bucket,
        key=blob_key,
        data=raw,
        content_type=mime,
    )
    logger.info("slide_upload_stored", project_id=str(pid), blob_key=blob_key, size=len(raw))

    # --- Create job record ---
    job_repo = JobRepository(session)
    job = await job_repo.create(task_name="slide_ingestion", related_entity_id=pid)
    await session.commit()

    # --- Enqueue Celery task ---
    ingest_slides.delay(
        project_id=str(pid),
        blob_key=blob_key,
        job_id=str(job.id),
        mime_type=mime,
    )

    return SlideUploadResponse(job_id=job.id, project_id=pid, status="queued")
