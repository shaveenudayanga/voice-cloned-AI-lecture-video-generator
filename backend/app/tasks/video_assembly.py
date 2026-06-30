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
    name="video_assembly",
    acks_late=True,
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def assemble_video(
    self: Task,
    project_id: str,
    job_id: str,
) -> dict[str, object]:
    """Assemble ordered slide PNGs and audio clips into a final MP4.

    Idempotent: re-running overwrites the existing artifact row and storage blobs.
    Model warm-up is not needed here (ffmpeg subprocess, no GPU model loading).
    """
    logger.info("task_video_assembly_start", project_id=project_id, job_id=job_id)
    return run_async(_run(project_id=project_id, job_id=job_id))


async def _run(project_id: str, job_id: str) -> dict[str, object]:
    from app.core.config import settings
    from app.db.repositories.audio_clip_repository import AudioClipRepository
    from app.db.repositories.job_repository import JobRepository
    from app.db.repositories.script_repository import ScriptRepository
    from app.db.repositories.slide_repository import SlideRepository
    from app.db.repositories.video_artifact_repository import VideoArtifactRepository
    from app.db.session import get_task_session
    from app.domain.value_objects import BlobKey
    from app.services.storage.factory import get_blob_store
    from app.services.video.assembler import SlideAudioPair, VideoAssembler

    pid = uuid.UUID(project_id)
    jid = uuid.UUID(job_id)

    store = get_blob_store()
    session = await get_task_session()

    try:
        job_repo = JobRepository(session)
        slide_repo = SlideRepository(session)
        script_repo = ScriptRepository(session)
        clip_repo = AudioClipRepository(session)
        artifact_repo = VideoArtifactRepository(session)

        await job_repo.update_status(jid, "running", progress_pct=5)
        await session.commit()

        # Load all slides (ordered)
        slides = await slide_repo.list_by_project(pid)
        if not slides:
            raise ValueError(f"No slides found for project {project_id}")

        clips = await clip_repo.list_by_project(pid)
        clip_by_slide = {c.slide_id: c for c in clips}

        missing = [sl.id for sl in slides if sl.id not in clip_by_slide]
        if missing:
            raise ValueError(f"{len(missing)} slide(s) missing AudioClip — run synthesis first")

        await job_repo.update_status(jid, "running", progress_pct=15)
        await session.commit()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            pairs: list[SlideAudioPair] = []

            # Pull blobs to temp files
            for slide in slides:
                clip = clip_by_slide[slide.id]
                script = await script_repo.get_by_slide(slide.id)
                script_text = script.text if script is not None else ""

                img_bytes = await store.get(
                    bucket=slide.image_blob.bucket,
                    key=slide.image_blob.key,
                )
                audio_bytes = await store.get(
                    bucket=clip.audio_blob.bucket,
                    key=clip.audio_blob.key,
                )

                img_path = tmp / f"slide_{slide.order_index:04d}.png"
                audio_path = tmp / f"audio_{slide.order_index:04d}.wav"
                img_path.write_bytes(img_bytes)
                audio_path.write_bytes(audio_bytes)

                pairs.append(
                    SlideAudioPair(
                        order_index=slide.order_index,
                        image_path=img_path,
                        audio_path=audio_path,
                        script_text=script_text,
                        duration_seconds=clip.duration_seconds,
                    )
                )

            await job_repo.update_status(jid, "running", progress_pct=30)
            await session.commit()

            output_path = tmp / "lecture.mp4"
            srt_path = tmp / "lecture.srt"

            assembler = VideoAssembler(use_hwaccel=settings.ffmpeg_hwaccel)
            result = await assembler.assemble(
                slides=pairs,
                output_path=output_path,
                srt_output_path=srt_path,
            )

            await job_repo.update_status(jid, "running", progress_pct=80)
            await session.commit()

            # Upload MP4
            video_key = f"projects/{project_id}/output/lecture.mp4"
            await store.ensure_bucket(settings.storage_bucket)
            mp4_bytes = result.output_path.read_bytes()
            await store.put(
                bucket=settings.storage_bucket,
                key=video_key,
                data=mp4_bytes,
                content_type="video/mp4",
            )

            # Upload SRT
            srt_key = f"projects/{project_id}/output/lecture.srt"
            srt_bytes = result.srt_path.read_bytes()
            await store.put(
                bucket=settings.storage_bucket,
                key=srt_key,
                data=srt_bytes,
                content_type="text/plain; charset=utf-8",
            )

        # Upsert VideoArtifact row
        artifact = await artifact_repo.upsert(
            project_id=pid,
            video_blob=BlobKey(bucket=settings.storage_bucket, key=video_key),
            srt_blob=BlobKey(bucket=settings.storage_bucket, key=srt_key),
            total_duration_seconds=result.total_duration_seconds,
            slide_count=len(pairs),
            ffmpeg_version=result.ffmpeg_version,
        )

        await job_repo.update_status(
            jid,
            "success",
            progress_pct=100,
            result_payload={
                "artifact_id": str(artifact.id),
                "project_id": project_id,
                "total_duration_s": result.total_duration_seconds,
                "slide_count": len(pairs),
            },
        )
        await session.commit()

        logger.info(
            "task_video_assembly_complete",
            project_id=project_id,
            artifact_id=str(artifact.id),
            duration_s=result.total_duration_seconds,
        )
        return {"status": "ok", "project_id": project_id, "artifact_id": str(artifact.id)}

    except Exception as exc:
        await job_repo.update_status(jid, "failed", error_message=str(exc))
        await session.commit()
        logger.error("task_video_assembly_failed", project_id=project_id, error=str(exc))
        raise

    finally:
        await session.close()
