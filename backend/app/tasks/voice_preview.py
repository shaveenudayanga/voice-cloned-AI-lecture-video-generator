# SPDX-License-Identifier: Apache-2.0
import uuid

import structlog
from celery import Task

from app.tasks._async_bridge import run_async
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_PREVIEW_SENTENCE = "Hello, this is a quick voice clone test. If this sounds right, we are ready to proceed."


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="voice_preview",
    acks_late=True,
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def synthesize_preview(
    self: Task,
    voice_profile_id: str,
    job_id: str,
) -> dict[str, object]:
    """Synthesize a short test sentence to confirm clone quality after recording.

    Phase 3 stub: updates job status immediately with a placeholder result.
    Full TTS synthesis is implemented in Phase 5.
    """
    logger.info("task_voice_preview_start", voice_profile_id=voice_profile_id, job_id=job_id)
    return run_async(_run(voice_profile_id=voice_profile_id, job_id=job_id))


async def _run(voice_profile_id: str, job_id: str) -> dict[str, object]:
    from app.db.repositories.job_repository import JobRepository
    from app.db.session import get_task_session

    jid = uuid.UUID(job_id)
    session = await get_task_session()

    try:
        job_repo = JobRepository(session)
        await job_repo.update_status(
            jid,
            "success",
            progress_pct=100,
            result_payload={
                "voice_profile_id": voice_profile_id,
                "message": "TTS not yet available — implement in Phase 5",
                "preview_audio_key": None,
            },
        )
        await session.commit()
        logger.info("task_voice_preview_complete", voice_profile_id=voice_profile_id)
        return {"status": "ok", "voice_profile_id": voice_profile_id, "phase": 3}

    except Exception as exc:
        logger.error("task_voice_preview_failed", voice_profile_id=voice_profile_id, error=str(exc))
        raise

    finally:
        await session.close()
