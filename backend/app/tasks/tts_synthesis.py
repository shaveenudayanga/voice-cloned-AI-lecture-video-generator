# SPDX-License-Identifier: Apache-2.0
import tempfile
import uuid
from pathlib import Path

import structlog
from celery import Task

from app.tasks._async_bridge import run_async
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="tts_synthesis",
    queue="gpu",
    acks_late=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def synthesize_slide(
    self: Task,
    slide_id: str,
    project_id: str,
    voice_profile_id: str,
    job_id: str,
) -> dict[str, object]:
    """Synthesize audio for one slide script using the active voice profile.

    Cache-skip: if the synthesis_fingerprint matches an existing AudioClip for this
    slide, the TTS model is not called — only the job status is updated (§7.3 lever 5).
    Idempotent: re-running produces the same result, never duplicate side effects.
    """
    logger.info(
        "task_tts_synthesis_start",
        slide_id=slide_id,
        voice_profile_id=voice_profile_id,
        job_id=job_id,
    )
    return run_async(
        _run(
            slide_id=slide_id,
            project_id=project_id,
            voice_profile_id=voice_profile_id,
            job_id=job_id,
        )
    )


async def _run(
    slide_id: str,
    project_id: str,
    voice_profile_id: str,
    job_id: str,
) -> dict[str, object]:
    from app.core.config import settings
    from app.db.repositories.audio_clip_repository import (
        AudioClipRepository,
        compute_synthesis_fingerprint,
    )
    from app.db.repositories.job_repository import JobRepository
    from app.db.repositories.script_repository import ScriptRepository
    from app.db.repositories.slide_repository import SlideRepository
    from app.db.repositories.voice_profile_repository import VoiceProfileRepository
    from app.db.session import get_task_session
    from app.domain.value_objects import BlobKey
    from app.services.storage.factory import get_blob_store
    from app.services.tts.factory import get_tts_engine_with_fallback

    sid = uuid.UUID(slide_id)
    pid = uuid.UUID(project_id)
    vpid = uuid.UUID(voice_profile_id)
    jid = uuid.UUID(job_id)

    store = get_blob_store()
    session = await get_task_session()

    try:
        job_repo = JobRepository(session)
        slide_repo = SlideRepository(session)
        script_repo = ScriptRepository(session)
        voice_repo = VoiceProfileRepository(session)
        clip_repo = AudioClipRepository(session)

        await job_repo.update_status(jid, "running", progress_pct=5)
        await session.commit()

        # Load slide and its script
        slide = await slide_repo.get(sid)
        if slide is None:
            raise ValueError(f"Slide {slide_id} not found")

        script = await script_repo.get_by_slide(sid)
        if script is None:
            raise ValueError(f"No script found for slide {slide_id}")

        voice = await voice_repo.get(vpid)
        if voice is None:
            raise ValueError(f"VoiceProfile {voice_profile_id} not found")

        # Compute fingerprint and check cache-skip ------------------------------------------------
        fingerprint = compute_synthesis_fingerprint(
            script_hash=script.script_hash,
            voice_profile_id=voice_profile_id,
            tts_engine=voice.tts_engine,
            tts_params=voice.tts_params,
        )

        existing = await clip_repo.get_by_fingerprint(sid, fingerprint)
        if existing is not None:
            logger.info(
                "tts_synthesis_cache_hit",
                slide_id=slide_id,
                fingerprint=fingerprint,
                clip_id=str(existing.id),
            )
            await job_repo.update_status(
                jid,
                "success",
                progress_pct=100,
                result_payload={
                    "audio_clip_id": str(existing.id),
                    "slide_id": slide_id,
                    "cache_hit": True,
                },
            )
            await session.commit()
            return {"status": "ok", "slide_id": slide_id, "cache_hit": True}

        await job_repo.update_status(jid, "running", progress_pct=20)
        await session.commit()

        # Pull reference audio -------------------------------------------------------------------
        ref_bytes = await store.get(
            bucket=voice.audio_blob.bucket,
            key=voice.audio_blob.key,
        )
        logger.info("tts_synthesis_ref_audio_fetched", slide_id=slide_id, size=len(ref_bytes))

        await job_repo.update_status(jid, "running", progress_pct=35)
        await session.commit()

        # Synthesize -----------------------------------------------------------------------------
        tts = get_tts_engine_with_fallback()

        with tempfile.TemporaryDirectory() as tmpdir:
            ref_path = Path(tmpdir) / "ref.wav"
            out_path = Path(tmpdir) / "out.wav"
            ref_path.write_bytes(ref_bytes)

            result = await tts.synthesize(
                text=script.text,
                reference_audio_path=ref_path,
                output_path=out_path,
                pronunciation_hints=script.pronunciation_hints,
            )

            audio_bytes = out_path.read_bytes()

        logger.info(
            "tts_synthesis_complete",
            slide_id=slide_id,
            duration_s=result.duration_seconds,
            engine=result.engine_used,
            used_gpu=result.used_gpu,
        )

        await job_repo.update_status(jid, "running", progress_pct=75)
        await session.commit()

        # Upload to object storage ---------------------------------------------------------------
        blob_key = f"projects/{project_id}/audio/{slide.order_index}.wav"
        await store.ensure_bucket(settings.storage_bucket)
        await store.put(
            bucket=settings.storage_bucket,
            key=blob_key,
            data=audio_bytes,
            content_type="audio/wav",
        )

        # Upsert AudioClip row -------------------------------------------------------------------
        clip = await clip_repo.upsert(
            project_id=pid,
            slide_id=sid,
            script_id=script.id,
            voice_profile_id=vpid,
            audio_blob=BlobKey(bucket=settings.storage_bucket, key=blob_key),
            duration_seconds=result.duration_seconds,
            engine_used=result.engine_used,
            synthesis_fingerprint=fingerprint,
        )

        await job_repo.update_status(
            jid,
            "success",
            progress_pct=100,
            result_payload={
                "audio_clip_id": str(clip.id),
                "slide_id": slide_id,
                "duration_s": result.duration_seconds,
                "engine_used": result.engine_used,
                "used_gpu": result.used_gpu,
                "cache_hit": False,
            },
        )
        await session.commit()

        logger.info("task_tts_synthesis_complete", slide_id=slide_id, clip_id=str(clip.id))
        return {"status": "ok", "slide_id": slide_id, "clip_id": str(clip.id)}

    except Exception as exc:
        await job_repo.update_status(jid, "failed", error_message=str(exc))
        await session.commit()
        logger.error("task_tts_synthesis_failed", slide_id=slide_id, error=str(exc))
        raise

    finally:
        await session.close()
