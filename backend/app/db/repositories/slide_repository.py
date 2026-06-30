# SPDX-License-Identifier: Apache-2.0
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.slide import SlideModel
from app.domain.entities import Slide
from app.domain.value_objects import BlobKey


def _to_entity(m: SlideModel) -> Slide:
    return Slide(
        id=m.id,
        project_id=m.project_id,
        order_index=m.order_index,
        image_blob=BlobKey(bucket=m.image_blob_bucket, key=m.image_blob_key),
        extracted_text=m.extracted_text,
        created_at=m.created_at,
    )


class SlideRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        project_id: uuid.UUID,
        order_index: int,
        image_blob: BlobKey,
        extracted_text: str,
    ) -> Slide:
        now = datetime.now(UTC)
        model = SlideModel(
            id=uuid.uuid4(),
            project_id=project_id,
            order_index=order_index,
            image_blob_bucket=image_blob.bucket,
            image_blob_key=image_blob.key,
            extracted_text=extracted_text,
            created_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def get(self, slide_id: uuid.UUID) -> Slide | None:
        result = await self._session.execute(select(SlideModel).where(SlideModel.id == slide_id))
        m = result.scalar_one_or_none()
        return _to_entity(m) if m is not None else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[Slide]:
        result = await self._session.execute(
            select(SlideModel).where(SlideModel.project_id == project_id).order_by(SlideModel.order_index)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def delete_by_project(self, project_id: uuid.UUID) -> None:
        await self._session.execute(delete(SlideModel).where(SlideModel.project_id == project_id))
