# SPDX-License-Identifier: Apache-2.0
import structlog
from celery import Task

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="tts_synthesis",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def synthesize_slide(self: Task, slide_id: str, voice_profile_id: str) -> dict[str, object]:
    """Synthesize audio for one slide script using the active voice profile. Phase 5."""
    logger.info("task_tts_synthesis_start", slide_id=slide_id, voice_profile_id=voice_profile_id)
    # Phase 5 implementation — includes cache-skip on AudioFingerprint
    logger.info("task_tts_synthesis_complete", slide_id=slide_id)
    return {"status": "ok", "slide_id": slide_id}
