# SPDX-License-Identifier: Apache-2.0
import structlog
from celery import Task

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="voice_ingestion",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def ingest_voice(self: Task, voice_profile_id: str) -> dict[str, object]:
    """Store recording, run Whisper transcription, persist style-reference transcript. Phase 3."""
    logger.info("task_voice_ingestion_start", voice_profile_id=voice_profile_id)
    # Phase 3 implementation
    logger.info("task_voice_ingestion_complete", voice_profile_id=voice_profile_id)
    return {"status": "ok", "voice_profile_id": voice_profile_id}
