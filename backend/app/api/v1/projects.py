# SPDX-License-Identifier: Apache-2.0
import uuid

import structlog
from fastapi import APIRouter, HTTPException

from app.api.deps import AuthDep, SessionDep, UserIdDep
from app.db.repositories.project_repository import ProjectRepository
from app.db.repositories.voice_profile_repository import VoiceProfileRepository
from app.domain.entities import Project
from app.schemas import ProjectCreateRequest, ProjectPatchRequest, ProjectResponse

router = APIRouter()
logger = structlog.get_logger(__name__)

_VALID_WIZARD_STEPS: frozenset[str] = frozenset({"upload", "voice", "scripts", "audio", "render", "done"})


def _to_response(p: Project) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        user_id=p.user_id,
        title=p.title,
        voice_profile_id=p.voice_profile_id,
        wizard_step=p.wizard_step,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> list[ProjectResponse]:
    """List all Projects for the current user."""
    repo = ProjectRepository(session)
    projects = await repo.list_by_user(user_id)
    return [_to_response(p) for p in projects]


@router.post("/projects", status_code=201, response_model=ProjectResponse)
async def create_project(
    body: ProjectCreateRequest,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> ProjectResponse:
    """Create a new Project and enter the wizard at the upload step."""
    repo = ProjectRepository(session)
    project = await repo.create(user_id=user_id, title=body.title)
    await session.commit()
    logger.info("project_created", project_id=str(project.id), user_id=str(user_id))
    return _to_response(project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> ProjectResponse:
    """Retrieve a single Project."""
    repo = ProjectRepository(session)
    project = await repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_response(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def patch_project(
    project_id: uuid.UUID,
    body: ProjectPatchRequest,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> ProjectResponse:
    """Update voice_profile_id or wizard_step on a Project.

    Setting voice_profile_id enables re-use of an existing VoiceProfile without
    re-recording (ADR-0009). The profile must belong to the current user.
    """
    project_repo = ProjectRepository(session)
    project = await project_repo.get(project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.voice_profile_id is not None:
        voice_repo = VoiceProfileRepository(session)
        profile = await voice_repo.get(body.voice_profile_id)
        if profile is None or profile.user_id != user_id:
            raise HTTPException(status_code=404, detail="VoiceProfile not found")
        updated = await project_repo.update_voice_profile(project_id, body.voice_profile_id)
        if updated is None:
            raise HTTPException(status_code=404, detail="Project not found")
        project = updated

    if body.wizard_step is not None:
        if body.wizard_step not in _VALID_WIZARD_STEPS:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid wizard_step. Must be one of: {sorted(_VALID_WIZARD_STEPS)}",
            )
        updated_step = await project_repo.update_wizard_step(
            project_id,
            body.wizard_step,  # type: ignore[arg-type]
        )
        if updated_step is None:
            raise HTTPException(status_code=404, detail="Project not found")
        project = updated_step

    await session.commit()
    return _to_response(project)
