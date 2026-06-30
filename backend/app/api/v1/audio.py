# SPDX-License-Identifier: Apache-2.0
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request

from app.api.deps import AuthDep, SessionDep, UserIdDep
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.repositories.audio_clip_repository import AudioClipRepository
from app.db.repositories.job_repository import JobRepository
from app.db.repositories.project_repository import ProjectRepository
from app.db.repositories.script_repository import ScriptRepository
from app.db.repositories.slide_repository import SlideRepository
from app.domain.entities import AudioClip
from app.schemas import AudioClipItem, AudioSynthesizeResponse, SlideAudioSynthesizeResponse
from app.tasks.tts_synthesis import synthesize_slide

router = APIRouter()
logger = structlog.get_logger(__name__)


def _to_clip_item(clip: AudioClip, order_index: int) -> AudioClipItem:
    return AudioClipItem(
        id=clip.id,
        slide_id=clip.slide_id,
        order_index=order_index,
        audio_blob_key=str(clip.audio_blob),
        duration_seconds=clip.duration_seconds,
        engine_used=clip.engine_used,
        synthesis_fingerprint=clip.synthesis_fingerprint,
    )


@router.post(
    "/projects/{project_id}/audio/synthesize",
    status_code=202,
    response_model=AudioSynthesizeResponse,
)
@limiter.limit(settings.rate_limit_generate)
async def trigger_audio_synthesis(
    request: Request,
    project_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> AudioSynthesizeResponse:
    """Fan-out: enqueue one tts_synthesis task per slide.

    Requires all slides to have scripts and the project to have a voice_profile_id set.
    Returns 202 immediately; use GET /jobs/{id} to track each slide's progress.
    Cache-skip is handled inside each task — only slides whose fingerprint changed
    will call the TTS engine (§7.3 lever 5).
    """
    project_repo = ProjectRepository(session)
    slide_repo = SlideRepository(session)
    script_repo = ScriptRepository(session)
    job_repo = JobRepository(session)

    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.voice_profile_id is None:
        raise HTTPException(
            status_code=422,
            detail="Project has no voice profile selected. Set voice_profile_id first.",
        )

    slides = await slide_repo.list_by_project(project_id)
    if not slides:
        raise HTTPException(status_code=422, detail="No slides found for this project")

    scripts = await script_repo.list_by_project(project_id)
    scripted_slide_ids = {s.slide_id for s in scripts}
    missing = [sl.id for sl in slides if sl.id not in scripted_slide_ids]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"{len(missing)} slide(s) are missing scripts. Generate scripts first.",
        )

    # Enqueue one synthesis job per slide — fan-out for parallelism (§7.1)
    job_ids: list[uuid.UUID] = []
    for slide in slides:
        job = await job_repo.create(
            task_name="tts_synthesis",
            related_entity_id=slide.id,
        )
        job_ids.append(job.id)

    await session.commit()

    for slide, job_id in zip(slides, job_ids, strict=True):
        synthesize_slide.delay(
            slide_id=str(slide.id),
            project_id=str(project_id),
            voice_profile_id=str(project.voice_profile_id),
            job_id=str(job_id),
        )

    logger.info(
        "audio_synthesis_queued",
        project_id=str(project_id),
        slide_count=len(slides),
        user_id=str(user_id),
    )
    return AudioSynthesizeResponse(
        job_ids=job_ids,
        slide_count=len(slides),
        status="queued",
    )


@router.post(
    "/projects/{project_id}/audio/{slide_id}/synthesize",
    status_code=202,
    response_model=SlideAudioSynthesizeResponse,
)
async def synthesize_slide_audio(
    project_id: uuid.UUID,
    slide_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> SlideAudioSynthesizeResponse:
    """Enqueue TTS synthesis for a single slide only.

    Separate from the fan-out POST /audio/synthesize — targets one slide,
    returns one job_id. Cache-skip still applies inside the task.
    Requires the slide to have a script and the project to have voice_profile_id set.
    """
    project_repo = ProjectRepository(session)
    slide_repo = SlideRepository(session)
    script_repo = ScriptRepository(session)
    job_repo = JobRepository(session)

    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.voice_profile_id is None:
        raise HTTPException(
            status_code=422,
            detail="Project has no voice profile selected. Set voice_profile_id first.",
        )

    slide = await slide_repo.get(slide_id)
    if slide is None or slide.project_id != project_id:
        raise HTTPException(status_code=404, detail="Slide not found in this project")

    script = await script_repo.get_by_slide(slide_id)
    if script is None:
        raise HTTPException(
            status_code=422,
            detail="Slide has no script. Generate or save a script first.",
        )

    job = await job_repo.create(task_name="tts_synthesis", related_entity_id=slide.id)
    await session.commit()

    synthesize_slide.delay(
        slide_id=str(slide.id),
        project_id=str(project_id),
        voice_profile_id=str(project.voice_profile_id),
        job_id=str(job.id),
    )

    logger.info(
        "slide_audio_synthesis_queued",
        project_id=str(project_id),
        slide_id=str(slide_id),
        job_id=str(job.id),
    )
    return SlideAudioSynthesizeResponse(
        job_id=job.id,
        slide_id=slide.id,
        status="queued",
    )


@router.get(
    "/projects/{project_id}/audio/",
    response_model=list[AudioClipItem],
)
async def list_audio_clips(
    project_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> list[AudioClipItem]:
    """Return all synthesized audio clips for a project, ordered by slide index."""
    project_repo = ProjectRepository(session)
    slide_repo = SlideRepository(session)
    clip_repo = AudioClipRepository(session)

    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    slides = await slide_repo.list_by_project(project_id)
    slide_order: dict[uuid.UUID, int] = {s.id: s.order_index for s in slides}

    clips = await clip_repo.list_by_project(project_id)
    # Sort by slide order_index for stable ordering
    clips.sort(key=lambda c: slide_order.get(c.slide_id, 0))

    return [_to_clip_item(clip, slide_order.get(clip.slide_id, 0)) for clip in clips]
