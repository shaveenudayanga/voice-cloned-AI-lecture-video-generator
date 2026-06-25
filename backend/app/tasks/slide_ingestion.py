# SPDX-License-Identifier: Apache-2.0
import uuid

import structlog
from celery import Task

from app.tasks._async_bridge import run_async
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="slide_ingestion",
    acks_late=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def ingest_slides(
    self: Task,
    project_id: str,
    blob_key: str,
    job_id: str,
    mime_type: str,
) -> dict[str, object]:
    """Parse uploaded slide deck into per-page PNGs and persist Slide rows.

    Idempotent: deletes existing Slide rows and blobs for this project before
    re-ingesting, so a re-upload always produces a clean state.
    """
    logger.info("task_slide_ingestion_start", project_id=project_id, job_id=job_id)
    return run_async(_run(project_id=project_id, blob_key=blob_key, job_id=job_id, mime_type=mime_type))


async def _run(project_id: str, blob_key: str, job_id: str, mime_type: str) -> dict[str, object]:
    from app.core.config import settings
    from app.db.repositories.job_repository import JobRepository
    from app.db.repositories.slide_repository import SlideRepository
    from app.db.session import get_task_session
    from app.domain.value_objects import BlobKey
    from app.services.slides.factory import get_slide_parser
    from app.services.storage.factory import get_blob_store

    pid = uuid.UUID(project_id)
    jid = uuid.UUID(job_id)
    store = get_blob_store()
    session = await get_task_session()

    try:
        job_repo = JobRepository(session)
        slide_repo = SlideRepository(session)

        # Mark running
        await job_repo.update_status(jid, "running", progress_pct=5)
        await session.commit()

        # Pull raw file from SeaweedFS
        raw_bytes = await store.get(bucket=settings.storage_bucket, key=blob_key)
        logger.info("slide_ingestion_downloaded", job_id=job_id, size=len(raw_bytes))

        await job_repo.update_status(jid, "running", progress_pct=15)
        await session.commit()

        # Parse slides
        parser = get_slide_parser(mime_type)
        parsed_slides = await parser.parse(raw_bytes)
        logger.info("slide_ingestion_parsed", job_id=job_id, count=len(parsed_slides))

        await job_repo.update_status(jid, "running", progress_pct=40)
        await session.commit()

        # Idempotency: delete existing Slide rows and blobs for this project
        existing = await slide_repo.list_by_project(pid)
        for existing_slide in existing:
            try:
                await store.delete(
                    bucket=existing_slide.image_blob.bucket,
                    key=existing_slide.image_blob.key,
                )
            except Exception:
                logger.warning("slide_ingestion_delete_blob_failed", key=str(existing_slide.image_blob))
        await slide_repo.delete_by_project(pid)
        await session.commit()

        # Upload PNGs and persist Slide rows
        total = len(parsed_slides)
        for i, ps in enumerate(parsed_slides):
            png_key = f"projects/{pid}/slides/{ps.order_index}.png"
            await store.put(
                bucket=settings.storage_bucket,
                key=png_key,
                data=ps.image_png,
                content_type="image/png",
            )
            await slide_repo.create(
                project_id=pid,
                order_index=ps.order_index,
                image_blob=BlobKey(bucket=settings.storage_bucket, key=png_key),
                extracted_text=ps.extracted_text,
            )
            pct = 40 + int(55 * (i + 1) / total)
            await job_repo.update_status(jid, "running", progress_pct=pct)
            await session.commit()

        # Done
        await job_repo.update_status(
            jid,
            "success",
            progress_pct=100,
            result_payload={"slide_count": total, "project_id": project_id},
        )
        await session.commit()
        logger.info("task_slide_ingestion_complete", project_id=project_id, slide_count=total)
        return {"status": "ok", "project_id": project_id, "slide_count": total}

    except Exception as exc:
        await job_repo.update_status(jid, "failed", error_message=str(exc))
        await session.commit()
        logger.error("task_slide_ingestion_failed", project_id=project_id, error=str(exc))
        raise

    finally:
        await session.close()
