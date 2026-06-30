# SPDX-License-Identifier: Apache-2.0
import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import ProjectModel
from app.domain.entities import Project, WizardStepLiteral


def _to_entity(m: ProjectModel) -> Project:
    return Project(
        id=m.id,
        user_id=m.user_id,
        title=m.title,
        voice_profile_id=m.voice_profile_id,
        wizard_step=cast(WizardStepLiteral, m.wizard_step),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, title: str) -> Project:
        now = datetime.now(UTC)
        model = ProjectModel(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            voice_profile_id=None,
            wizard_step="upload",
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def get(self, project_id: uuid.UUID) -> Project | None:
        result = await self._session.execute(select(ProjectModel).where(ProjectModel.id == project_id))
        m = result.scalar_one_or_none()
        return _to_entity(m) if m is not None else None

    async def list_by_user(self, user_id: uuid.UUID) -> list[Project]:
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.user_id == user_id).order_by(ProjectModel.created_at.desc())
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def list_by_voice_profile(self, voice_profile_id: uuid.UUID) -> list[Project]:
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.voice_profile_id == voice_profile_id)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def update_voice_profile(
        self,
        project_id: uuid.UUID,
        voice_profile_id: uuid.UUID | None,
    ) -> Project | None:
        result = await self._session.execute(select(ProjectModel).where(ProjectModel.id == project_id))
        m = result.scalar_one_or_none()
        if m is None:
            return None
        m.voice_profile_id = voice_profile_id
        m.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _to_entity(m)

    async def update_wizard_step(
        self,
        project_id: uuid.UUID,
        wizard_step: WizardStepLiteral,
    ) -> Project | None:
        result = await self._session.execute(select(ProjectModel).where(ProjectModel.id == project_id))
        m = result.scalar_one_or_none()
        if m is None:
            return None
        m.wizard_step = wizard_step
        m.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _to_entity(m)
