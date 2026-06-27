# SPDX-License-Identifier: Apache-2.0
import uuid

import structlog
from fastapi import APIRouter, HTTPException

from app.api.deps import AuthDep, SessionDep, UserIdDep
from app.db.repositories.job_repository import JobRepository
from app.db.repositories.project_repository import ProjectRepository
from app.db.repositories.script_repository import ScriptRepository
from app.db.repositories.slide_repository import SlideRepository
from app.domain.entities import Script
from app.schemas import (
    ScriptGenerateResponse,
    ScriptListItem,
    ScriptPatchRequest,
    ScriptResponse,
    SlideScriptRegenerateResponse,
)
from app.tasks.script_generation import generate_script

router = APIRouter()
logger = structlog.get_logger(__name__)


def _to_response(script: Script) -> ScriptResponse:
    return ScriptResponse(
        id=script.id,
        slide_id=script.slide_id,
        project_id=script.project_id,
        text=script.text,
        estimated_reading_seconds=script.estimated_reading_seconds,
        pronunciation_hints=script.pronunciation_hints,
        version=script.version,
        script_hash=script.script_hash,
        updated_at=script.updated_at,
    )


@router.post(
    "/projects/{project_id}/scripts/generate",
    status_code=202,
    response_model=ScriptGenerateResponse,
)
async def generate_scripts(
    project_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> ScriptGenerateResponse:
    """Enqueue per-slide script generation (fan-out) for a project.

    Requires slides to exist and a VoiceProfile to be set on the project.
    """
    project_repo = ProjectRepository(session)
    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.voice_profile_id is None:
        raise HTTPException(
            status_code=422,
            detail="Project has no VoiceProfile set. Assign one before generating scripts.",
        )

    slide_repo = SlideRepository(session)
    slides = await slide_repo.list_by_project(project_id)
    if not slides:
        raise HTTPException(
            status_code=422,
            detail="Project has no slides. Upload a slide deck first.",
        )

    job_repo = JobRepository(session)
    job_ids: list[uuid.UUID] = []
    for slide in slides:
        job = await job_repo.create(task_name="script_generation", related_entity_id=slide.id)
        job_ids.append(job.id)

    await session.commit()

    for slide, job_id in zip(slides, job_ids, strict=True):
        generate_script.delay(
            slide_id=str(slide.id),
            voice_profile_id=str(project.voice_profile_id),
            job_id=str(job_id),
        )

    logger.info(
        "scripts_generation_queued",
        project_id=str(project_id),
        slide_count=len(slides),
    )
    return ScriptGenerateResponse(
        job_ids=job_ids,
        slide_count=len(slides),
        status="queued",
    )


@router.get(
    "/projects/{project_id}/scripts/",
    response_model=list[ScriptListItem],
)
async def list_scripts(
    project_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> list[ScriptListItem]:
    """Return all scripts for a project, ordered by slide index."""
    project_repo = ProjectRepository(session)
    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    slide_repo = SlideRepository(session)
    slides = await slide_repo.list_by_project(project_id)

    script_repo = ScriptRepository(session)
    scripts_by_slide = {
        s.slide_id: s
        for s in await script_repo.list_by_project(project_id)
    }

    items: list[ScriptListItem] = []
    for slide in slides:
        script = scripts_by_slide.get(slide.id)
        if script is not None:
            items.append(
                ScriptListItem(
                    id=script.id,
                    slide_id=script.slide_id,
                    order_index=slide.order_index,
                    text=script.text,
                    estimated_reading_seconds=script.estimated_reading_seconds,
                    pronunciation_hints=script.pronunciation_hints,
                    version=script.version,
                    script_hash=script.script_hash,
                )
            )

    return items


@router.get(
    "/projects/{project_id}/scripts/{script_id}",
    response_model=ScriptResponse,
)
async def get_script(
    project_id: uuid.UUID,
    script_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> ScriptResponse:
    """Return a single script by ID."""
    project_repo = ProjectRepository(session)
    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    script_repo = ScriptRepository(session)
    script = await script_repo.get(script_id)
    if script is None or script.project_id != project_id:
        raise HTTPException(status_code=404, detail="Script not found")

    return _to_response(script)


@router.post(
    "/projects/{project_id}/scripts/{slide_id}/regenerate",
    status_code=202,
    response_model=SlideScriptRegenerateResponse,
)
async def regenerate_slide_script(
    project_id: uuid.UUID,
    slide_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> SlideScriptRegenerateResponse:
    """Enqueue script generation for a single slide only.

    Separate from the fan-out POST /scripts/generate — targets one slide,
    returns one job_id. Requires voice_profile_id to be set on the project.
    """
    project_repo = ProjectRepository(session)
    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.voice_profile_id is None:
        raise HTTPException(
            status_code=422,
            detail="Project has no VoiceProfile set. Assign one before generating scripts.",
        )

    slide_repo = SlideRepository(session)
    slide = await slide_repo.get(slide_id)
    if slide is None or slide.project_id != project_id:
        raise HTTPException(status_code=404, detail="Slide not found in this project")

    job_repo = JobRepository(session)
    job = await job_repo.create(task_name="script_generation", related_entity_id=slide.id)
    await session.commit()

    generate_script.delay(
        slide_id=str(slide.id),
        voice_profile_id=str(project.voice_profile_id),
        job_id=str(job.id),
    )

    logger.info(
        "slide_script_regen_queued",
        project_id=str(project_id),
        slide_id=str(slide_id),
        job_id=str(job.id),
    )
    return SlideScriptRegenerateResponse(
        job_id=job.id,
        slide_id=slide.id,
        status="queued",
    )


@router.patch(
    "/projects/{project_id}/scripts/{script_id}",
    response_model=ScriptResponse,
)
async def patch_script(
    project_id: uuid.UUID,
    script_id: uuid.UUID,
    body: ScriptPatchRequest,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> ScriptResponse:
    """Update text and/or pronunciation_hints on a script.

    Recomputes script_hash and increments version when text changes.
    """
    project_repo = ProjectRepository(session)
    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    script_repo = ScriptRepository(session)
    script = await script_repo.get(script_id)
    if script is None or script.project_id != project_id:
        raise HTTPException(status_code=404, detail="Script not found")

    updated = await script_repo.update(
        script_id=script_id,
        text=body.text,
        pronunciation_hints=body.pronunciation_hints,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Script not found")

    await session.commit()
    return _to_response(updated)
