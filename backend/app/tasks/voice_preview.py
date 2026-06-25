# SPDX-License-Identifier: Apache-2.0
import structlog
from celery import Task

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_PREVIEW_SENTENCE = "Hello, this is a quick voice clone test. If this sounds right, we are ready to proceed."


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="voice_preview",
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def synthesize_preview(self: Task, voice_profile_id: str) -> dict[str, object]:
    """Synthesize one test sentence immediately after recording to catch bad clones. Phase 5."""
    logger.info("task_voice_preview_start", voice_profile_id=voice_profile_id)
    # Phase 5 implementation
    logger.info("task_voice_preview_complete", voice_profile_id=voice_profile_id)
    return {"status": "ok", "voice_profile_id": voice_profile_id}
