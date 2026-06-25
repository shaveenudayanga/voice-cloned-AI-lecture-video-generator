# SPDX-License-Identifier: Apache-2.0
import uuid

import structlog
from celery import Task

from app.tasks._async_bridge import run_async
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="voice_ingestion",
    acks_late=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def ingest_voice(
    self: Task,
    voice_profile_id: str,
    blob_key: str,
    job_id: str,
) -> dict[str, object]:
    """Transcribe a voice recording with Whisper and persist the style-reference transcript.

    Idempotent: safe to retry — always overwrites the transcript on re-run.
    """
    logger.info("task_voice_ingestion_start", voice_profile_id=voice_profile_id, job_id=job_id)
    return run_async(
        _run(voice_profile_id=voice_profile_id, blob_key=blob_key, job_id=job_id)
    )


async def _run(voice_profile_id: str, blob_key: str, job_id: str) -> dict[str, object]:
    from app.core.config import settings
    from app.db.repositories.job_repository import JobRepository
    from app.db.repositories.voice_profile_repository import VoiceProfileRepository
    from app.db.session import get_task_session
    from app.services.storage.factory import get_blob_store
    from app.services.transcription.factory import get_transcriber

    vpid = uuid.UUID(voice_profile_id)
    jid = uuid.UUID(job_id)
    store = get_blob_store()
    session = await get_task_session()

    try:
        job_repo = JobRepository(session)
        voice_repo = VoiceProfileRepository(session)

        await job_repo.update_status(jid, "running", progress_pct=5)
        await session.commit()

        # Pull the audio clip from SeaweedFS
        audio_bytes = await store.get(bucket=settings.storage_bucket, key=blob_key)
        logger.info("voice_ingestion_downloaded", job_id=job_id, size=len(audio_bytes))

        await job_repo.update_status(jid, "running", progress_pct=20)
        await session.commit()

        # Run Whisper transcription — model loaded once per worker (§7.3)
        transcriber = get_transcriber()
        result = await transcriber.transcribe(audio_bytes)
        logger.info(
            "voice_ingestion_transcribed",
            job_id=job_id,
            language=result.language,
            duration=result.duration_s,
            text_length=len(result.text),
        )

        await job_repo.update_status(jid, "running", progress_pct=80)
        await session.commit()

        # Persist style-reference transcript on the VoiceProfile (idempotent)
        await voice_repo.update_transcript(vpid, result.text)
        await job_repo.update_status(
            jid,
            "success",
            progress_pct=100,
            result_payload={
                "voice_profile_id": voice_profile_id,
                "language": result.language,
                "duration_s": result.duration_s,
                "transcript_length": len(result.text),
            },
        )
        await session.commit()

        logger.info("task_voice_ingestion_complete", voice_profile_id=voice_profile_id)
        return {"status": "ok", "voice_profile_id": voice_profile_id}

    except Exception as exc:
        await job_repo.update_status(jid, "failed", error_message=str(exc))
        await session.commit()
        logger.error("task_voice_ingestion_failed", voice_profile_id=voice_profile_id, error=str(exc))
        raise

    finally:
        await session.close()
