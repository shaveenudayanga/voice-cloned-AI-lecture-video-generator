# SPDX-License-Identifier: Apache-2.0
import tempfile
import uuid
from pathlib import Path

import structlog
from celery import Task

from app.tasks._async_bridge import run_async
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

_PREVIEW_SENTENCE = "Hello, this is a preview of my cloned voice for lecture recordings. How does this sound?"


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="voice_preview",
    queue="gpu",
    acks_late=True,
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def synthesize_preview(
    self: Task,
    voice_profile_id: str,
    user_id: str,
    job_id: str,
) -> dict[str, object]:
    """Synthesize a one-sentence clone-quality test immediately after voice recording.

    Lets the professor confirm clone quality in seconds before committing to a full
    30-slide synthesis run (§3.3 step 4, Phase 5).
    """
    logger.info("task_voice_preview_start", voice_profile_id=voice_profile_id, job_id=job_id)
    return run_async(_run(voice_profile_id=voice_profile_id, user_id=user_id, job_id=job_id))


async def _run(voice_profile_id: str, user_id: str, job_id: str) -> dict[str, object]:
    from app.core.config import settings
    from app.db.repositories.job_repository import JobRepository
    from app.db.repositories.voice_profile_repository import VoiceProfileRepository
    from app.db.session import get_task_session
    from app.services.storage.factory import get_blob_store
    from app.services.tts.factory import get_tts_engine_with_fallback

    vpid = uuid.UUID(voice_profile_id)
    jid = uuid.UUID(job_id)

    store = get_blob_store()
    session = await get_task_session()

    try:
        job_repo = JobRepository(session)
        voice_repo = VoiceProfileRepository(session)

        await job_repo.update_status(jid, "running", progress_pct=10)
        await session.commit()

        voice = await voice_repo.get(vpid)
        if voice is None:
            raise ValueError(f"VoiceProfile {voice_profile_id} not found")

        # Pull reference audio from SeaweedFS
        ref_bytes = await store.get(
            bucket=voice.audio_blob.bucket,
            key=voice.audio_blob.key,
        )
        logger.info(
            "voice_preview_ref_fetched",
            voice_profile_id=voice_profile_id,
            size=len(ref_bytes),
        )

        await job_repo.update_status(jid, "running", progress_pct=30)
        await session.commit()

        tts = get_tts_engine_with_fallback()

        with tempfile.TemporaryDirectory() as tmpdir:
            ref_path = Path(tmpdir) / "ref.wav"
            out_path = Path(tmpdir) / "preview.wav"
            ref_path.write_bytes(ref_bytes)

            result = await tts.synthesize_preview(
                text=_PREVIEW_SENTENCE,
                reference_audio_path=ref_path,
                output_path=out_path,
            )

            preview_bytes = out_path.read_bytes()

        logger.info(
            "voice_preview_synthesized",
            voice_profile_id=voice_profile_id,
            duration_s=result.duration_seconds,
            engine=result.engine_used,
            used_gpu=result.used_gpu,
        )

        await job_repo.update_status(jid, "running", progress_pct=75)
        await session.commit()

        # Upload preview WAV
        preview_key = f"users/{user_id}/voices/{voice_profile_id}_preview.wav"
        await store.ensure_bucket(settings.storage_bucket)
        await store.put(
            bucket=settings.storage_bucket,
            key=preview_key,
            data=preview_bytes,
            content_type="audio/wav",
        )

        # Persist preview blob key on VoiceProfile
        await voice_repo.update_preview_blob_key(vpid, preview_key)

        await job_repo.update_status(
            jid,
            "success",
            progress_pct=100,
            result_payload={
                "voice_profile_id": voice_profile_id,
                "preview_audio_key": preview_key,
                "duration_s": result.duration_seconds,
                "engine_used": result.engine_used,
                "used_gpu": result.used_gpu,
            },
        )
        await session.commit()

        logger.info("task_voice_preview_complete", voice_profile_id=voice_profile_id)
        return {"status": "ok", "voice_profile_id": voice_profile_id, "preview_key": preview_key}

    except Exception as exc:
        await job_repo.update_status(jid, "failed", error_message=str(exc))
        await session.commit()
        logger.error("task_voice_preview_failed", voice_profile_id=voice_profile_id, error=str(exc))
        raise

    finally:
        await session.close()
