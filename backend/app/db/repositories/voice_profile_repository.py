# SPDX-License-Identifier: Apache-2.0
import json
import uuid
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.voice_profile import VoiceProfileModel
from app.domain.entities import VoiceProfile
from app.domain.value_objects import BlobKey


def _to_entity(m: VoiceProfileModel) -> VoiceProfile:
    return VoiceProfile(
        id=m.id,
        user_id=m.user_id,
        display_name=m.display_name,
        audio_blob=BlobKey(bucket=m.audio_blob_bucket, key=m.audio_blob_key),
        style_reference_transcript=m.style_reference_transcript,
        extra_style_sample=m.extra_style_sample,
        tts_engine=cast(Literal["f5", "xtts"], m.tts_engine),
        tts_params=cast(dict[str, object], json.loads(m.tts_params)),
        is_default=m.is_default,
        created_at=m.created_at,
        updated_at=m.updated_at,
        preview_audio_blob_key=m.preview_audio_blob_key,
    )


class VoiceProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        display_name: str,
        audio_blob: BlobKey,
        tts_engine: str = "f5",
        tts_params: dict[str, object] | None = None,
        is_default: bool = False,
        profile_id: uuid.UUID | None = None,
    ) -> VoiceProfile:
        now = datetime.now(UTC)
        model = VoiceProfileModel(
            id=profile_id if profile_id is not None else uuid.uuid4(),
            user_id=user_id,
            display_name=display_name,
            audio_blob_bucket=audio_blob.bucket,
            audio_blob_key=audio_blob.key,
            style_reference_transcript="",
            extra_style_sample=None,
            tts_engine=tts_engine,
            tts_params=json.dumps(tts_params or {}),
            is_default=is_default,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def get(self, profile_id: uuid.UUID) -> VoiceProfile | None:
        result = await self._session.execute(
            select(VoiceProfileModel).where(VoiceProfileModel.id == profile_id)
        )
        m = result.scalar_one_or_none()
        return _to_entity(m) if m is not None else None

    async def list_by_user(self, user_id: uuid.UUID) -> list[VoiceProfile]:
        result = await self._session.execute(
            select(VoiceProfileModel)
            .where(VoiceProfileModel.user_id == user_id)
            .order_by(VoiceProfileModel.created_at.desc())
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(VoiceProfileModel).where(VoiceProfileModel.user_id == user_id)
        )
        return result.scalar_one()

    async def unset_default_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            update(VoiceProfileModel)
            .where(VoiceProfileModel.user_id == user_id)
            .values(is_default=False, updated_at=datetime.now(UTC))
        )

    async def update(
        self,
        profile_id: uuid.UUID,
        display_name: str | None = None,
        extra_style_sample: str | None = None,
        is_default: bool | None = None,
    ) -> VoiceProfile | None:
        result = await self._session.execute(
            select(VoiceProfileModel).where(VoiceProfileModel.id == profile_id)
        )
        m = result.scalar_one_or_none()
        if m is None:
            return None
        if display_name is not None:
            m.display_name = display_name
        if extra_style_sample is not None:
            m.extra_style_sample = extra_style_sample
        if is_default is not None:
            m.is_default = is_default
        m.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _to_entity(m)

    async def update_transcript(self, profile_id: uuid.UUID, transcript: str) -> None:
        await self._session.execute(
            update(VoiceProfileModel)
            .where(VoiceProfileModel.id == profile_id)
            .values(style_reference_transcript=transcript, updated_at=datetime.now(UTC))
        )

    async def update_preview_blob_key(self, profile_id: uuid.UUID, blob_key: str) -> None:
        """Store the preview audio blob key after voice_preview task completes."""
        await self._session.execute(
            update(VoiceProfileModel)
            .where(VoiceProfileModel.id == profile_id)
            .values(preview_audio_blob_key=blob_key, updated_at=datetime.now(UTC))
        )

    async def delete(self, profile_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(VoiceProfileModel).where(VoiceProfileModel.id == profile_id)
        )
        m = result.scalar_one_or_none()
        if m is not None:
            await self._session.delete(m)
