# SPDX-License-Identifier: Apache-2.0
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.job import JobModel
from app.domain.entities import Job, JobStatusLiteral


def _to_entity(m: JobModel) -> Job:
    payload: dict[str, object] | None = None
    if m.result_payload is not None:
        payload = json.loads(m.result_payload)
    return Job(
        id=m.id,
        task_name=m.task_name,
        status=m.status,  # type: ignore[arg-type]
        progress_pct=m.progress_pct,
        result_payload=payload,
        error_message=m.error_message,
        related_entity_id=m.related_entity_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        task_name: str,
        related_entity_id: uuid.UUID | None = None,
    ) -> Job:
        now = datetime.now(UTC)
        model = JobModel(
            id=uuid.uuid4(),
            task_name=task_name,
            status="queued",
            progress_pct=0,
            related_entity_id=related_entity_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def get(self, job_id: uuid.UUID) -> Job | None:
        result = await self._session.execute(select(JobModel).where(JobModel.id == job_id))
        model = result.scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def update_status(
        self,
        job_id: uuid.UUID,
        status: JobStatusLiteral,
        progress_pct: int | None = None,
        error_message: str | None = None,
        result_payload: dict[str, object] | None = None,
    ) -> None:
        result = await self._session.execute(select(JobModel).where(JobModel.id == job_id))
        model = result.scalar_one_or_none()
        if model is None:
            return
        model.status = status
        model.updated_at = datetime.now(UTC)
        if progress_pct is not None:
            model.progress_pct = progress_pct
        if error_message is not None:
            model.error_message = error_message
        if result_payload is not None:
            model.result_payload = json.dumps(result_payload)
        await self._session.flush()
