# SPDX-License-Identifier: Apache-2.0
import uuid

import structlog
from celery import Task

from app.tasks._async_bridge import run_async
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="script_generation",
    acks_late=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def generate_script(
    self: Task,
    slide_id: str,
    voice_profile_id: str,
    job_id: str,
) -> dict[str, object]:
    """Generate a narration script for one slide, injecting the voice profile style reference.

    Idempotent: upserts the Script row — safe to retry and re-run.
    """
    logger.info("task_script_generation_start", slide_id=slide_id, job_id=job_id)
    return run_async(_run(slide_id=slide_id, voice_profile_id=voice_profile_id, job_id=job_id))


async def _run(
    slide_id: str,
    voice_profile_id: str,
    job_id: str,
) -> dict[str, object]:
    from app.core.config import settings
    from app.db.repositories.job_repository import JobRepository
    from app.db.repositories.script_repository import ScriptRepository
    from app.db.repositories.slide_repository import SlideRepository
    from app.db.repositories.voice_profile_repository import VoiceProfileRepository
    from app.db.session import get_task_session
    from app.services.script.factory import get_script_generator
    from app.services.storage.factory import get_blob_store

    sid = uuid.UUID(slide_id)
    vpid = uuid.UUID(voice_profile_id)
    jid = uuid.UUID(job_id)

    store = get_blob_store()
    session = await get_task_session()

    try:
        job_repo = JobRepository(session)
        slide_repo = SlideRepository(session)
        voice_repo = VoiceProfileRepository(session)
        script_repo = ScriptRepository(session)

        await job_repo.update_status(jid, "running", progress_pct=5)
        await session.commit()

        # Load slide: image bytes from SeaweedFS + extracted text
        slide = await slide_repo.get(sid)
        if slide is None:
            raise RuntimeError(f"Slide {slide_id} not found")

        image_bytes = await store.get(
            bucket=slide.image_blob.bucket,
            key=slide.image_blob.key,
        )
        logger.info("script_gen_slide_loaded", slide_id=slide_id, text_len=len(slide.extracted_text))

        await job_repo.update_status(jid, "running", progress_pct=20)
        await session.commit()

        # Load voice profile and combine style references
        profile = await voice_repo.get(vpid)
        if profile is None:
            raise RuntimeError(f"VoiceProfile {voice_profile_id} not found")

        style_reference: str | None = profile.style_reference_transcript or None
        if profile.extra_style_sample:
            style_reference = (
                f"{style_reference}\n\n{profile.extra_style_sample}" if style_reference else profile.extra_style_sample
            )

        # Carry forward any user-edited pronunciation hints from a previous script version
        existing_script = await script_repo.get_by_slide(sid)
        pronunciation_hints = existing_script.pronunciation_hints if existing_script is not None else None

        await job_repo.update_status(jid, "running", progress_pct=30)
        await session.commit()

        # Call the LLM adapter (model/client warm per §7.3)
        generator = get_script_generator()
        from app.core.metrics import llm_script_generation_total

        try:
            generated = await generator.generate(
                slide_image_bytes=image_bytes,
                slide_text=slide.extracted_text,
                style_reference=style_reference,
                pronunciation_hints=pronunciation_hints,
            )
        except Exception:
            llm_script_generation_total.labels(provider=settings.llm_provider, status="failure").inc()
            raise
        llm_script_generation_total.labels(provider=settings.llm_provider, status="success").inc()
        logger.info(
            "script_gen_generated",
            slide_id=slide_id,
            text_len=len(generated.text),
            reading_s=generated.estimated_reading_seconds,
        )

        await job_repo.update_status(jid, "running", progress_pct=80)
        await session.commit()

        # Upsert: create or overwrite the Script row (idempotent)
        script = await script_repo.upsert(
            slide_id=sid,
            project_id=slide.project_id,
            text=generated.text,
            estimated_reading_seconds=generated.estimated_reading_seconds,
            pronunciation_hints=generated.pronunciation_hints,
        )

        await job_repo.update_status(
            jid,
            "success",
            progress_pct=100,
            result_payload={
                "script_id": str(script.id),
                "slide_id": slide_id,
                "script_hash": script.script_hash,
                "version": script.version,
            },
        )
        await session.commit()

        logger.info(
            "task_script_generation_complete",
            slide_id=slide_id,
            script_id=str(script.id),
            version=script.version,
        )
        return {"status": "ok", "slide_id": slide_id, "script_id": str(script.id)}

    except Exception as exc:
        await job_repo.update_status(jid, "failed", error_message=str(exc))
        await session.commit()
        logger.error("task_script_generation_failed", slide_id=slide_id, error=str(exc))
        raise

    finally:
        await session.close()
