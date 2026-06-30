# SPDX-License-Identifier: Apache-2.0
import uuid

import structlog
from fastapi import APIRouter, HTTPException

from app.api.deps import AuthDep, SessionDep, UserIdDep
from app.db.repositories.audio_clip_repository import AudioClipRepository
from app.db.repositories.job_repository import JobRepository
from app.db.repositories.project_repository import ProjectRepository
from app.db.repositories.slide_repository import SlideRepository
from app.db.repositories.video_artifact_repository import VideoArtifactRepository
from app.domain.entities import VideoArtifact
from app.schemas import VideoArtifactResponse, VideoAssembleResponse
from app.tasks.video_assembly import assemble_video

router = APIRouter()
logger = structlog.get_logger(__name__)


def _to_artifact_response(artifact: VideoArtifact) -> VideoArtifactResponse:
    srt_key: str | None = str(artifact.srt_blob) if artifact.srt_blob is not None else None
    return VideoArtifactResponse(
        id=artifact.id,
        project_id=artifact.project_id,
        video_blob_key=str(artifact.video_blob),
        srt_blob_key=srt_key,
        total_duration_seconds=artifact.total_duration_seconds,
        slide_count=artifact.slide_count,
        ffmpeg_version=artifact.ffmpeg_version,
        created_at=artifact.created_at,
    )


@router.post(
    "/projects/{project_id}/video/assemble",
    status_code=202,
    response_model=VideoAssembleResponse,
)
async def trigger_video_assembly(
    project_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> VideoAssembleResponse:
    """Enqueue a video_assembly job for the project.

    Requires all slides to have AudioClips. Returns 202 immediately; poll
    GET /jobs/{job_id} for progress. Re-running overwrites the existing artifact.
    """
    project_repo = ProjectRepository(session)
    slide_repo = SlideRepository(session)
    clip_repo = AudioClipRepository(session)
    job_repo = JobRepository(session)

    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    slides = await slide_repo.list_by_project(project_id)
    if not slides:
        raise HTTPException(status_code=422, detail="No slides found for this project")

    clips = await clip_repo.list_by_project(project_id)
    clip_slide_ids = {c.slide_id for c in clips}
    missing = [sl.id for sl in slides if sl.id not in clip_slide_ids]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=(f"{len(missing)} slide(s) are missing audio clips. Run audio synthesis for all slides first."),
        )

    job = await job_repo.create(
        task_name="video_assembly",
        related_entity_id=project_id,
    )
    await session.commit()

    assemble_video.delay(
        project_id=str(project_id),
        job_id=str(job.id),
    )

    logger.info(
        "video_assembly_queued",
        project_id=str(project_id),
        slide_count=len(slides),
        job_id=str(job.id),
        user_id=str(user_id),
    )
    return VideoAssembleResponse(
        job_id=job.id,
        project_id=project_id,
        status="queued",
    )


@router.get(
    "/projects/{project_id}/video/",
    response_model=VideoArtifactResponse,
)
async def get_video_artifact(
    project_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> VideoArtifactResponse:
    """Return the assembled VideoArtifact for the project, or 404 if not yet assembled."""
    project_repo = ProjectRepository(session)
    artifact_repo = VideoArtifactRepository(session)

    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    artifact = await artifact_repo.get_by_project(project_id)
    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail="Video has not been assembled yet for this project",
        )

    return _to_artifact_response(artifact)
