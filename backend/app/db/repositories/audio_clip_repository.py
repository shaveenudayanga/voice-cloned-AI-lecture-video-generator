# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audio_clip import AudioClipModel
from app.domain.entities import AudioClip
from app.domain.value_objects import BlobKey


def compute_synthesis_fingerprint(
    script_hash: str,
    voice_profile_id: str,
    tts_engine: str,
    tts_params: dict[str, object],
) -> str:
    """SHA-256 of the four inputs that determine a unique synthesis output (§7.3 lever 5).

    Changing any of these makes a new fingerprint, invalidating the cached AudioClip
    and triggering re-synthesis for that slide only.
    """
    payload = (
        f"{script_hash}:{voice_profile_id}:{tts_engine}:"
        f"{json.dumps(tts_params, sort_keys=True)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _to_entity(m: AudioClipModel) -> AudioClip:
    return AudioClip(
        id=m.id,
        project_id=m.project_id,
        slide_id=m.slide_id,
        script_id=m.script_id,
        voice_profile_id=m.voice_profile_id,
        audio_blob=BlobKey(bucket=m.audio_blob_bucket, key=m.audio_blob_key),
        duration_seconds=m.duration_seconds,
        engine_used=m.engine_used,
        synthesis_fingerprint=m.synthesis_fingerprint,
        created_at=m.created_at,
    )


class AudioClipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_slide(self, slide_id: uuid.UUID) -> AudioClip | None:
        result = await self._session.execute(
            select(AudioClipModel).where(AudioClipModel.slide_id == slide_id)
        )
        m = result.scalar_one_or_none()
        return _to_entity(m) if m is not None else None

    async def get_by_fingerprint(
        self, slide_id: uuid.UUID, fingerprint: str
    ) -> AudioClip | None:
        """Return an existing clip if the synthesis fingerprint matches (cache-hit path)."""
        result = await self._session.execute(
            select(AudioClipModel).where(
                AudioClipModel.slide_id == slide_id,
                AudioClipModel.synthesis_fingerprint == fingerprint,
            )
        )
        m = result.scalar_one_or_none()
        return _to_entity(m) if m is not None else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[AudioClip]:
        result = await self._session.execute(
            select(AudioClipModel).where(AudioClipModel.project_id == project_id)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def upsert(
        self,
        project_id: uuid.UUID,
        slide_id: uuid.UUID,
        script_id: uuid.UUID,
        voice_profile_id: uuid.UUID,
        audio_blob: BlobKey,
        duration_seconds: float,
        engine_used: str,
        synthesis_fingerprint: str,
    ) -> AudioClip:
        """Insert a new AudioClip or replace the existing one for this slide (idempotent)."""
        now = datetime.now(UTC)

        result = await self._session.execute(
            select(AudioClipModel).where(AudioClipModel.slide_id == slide_id)
        )
        m = result.scalar_one_or_none()

        if m is None:
            m = AudioClipModel(
                id=uuid.uuid4(),
                project_id=project_id,
                slide_id=slide_id,
                script_id=script_id,
                voice_profile_id=voice_profile_id,
                audio_blob_bucket=audio_blob.bucket,
                audio_blob_key=audio_blob.key,
                duration_seconds=duration_seconds,
                engine_used=engine_used,
                synthesis_fingerprint=synthesis_fingerprint,
                created_at=now,
            )
            self._session.add(m)
        else:
            m.script_id = script_id
            m.voice_profile_id = voice_profile_id
            m.audio_blob_bucket = audio_blob.bucket
            m.audio_blob_key = audio_blob.key
            m.duration_seconds = duration_seconds
            m.engine_used = engine_used
            m.synthesis_fingerprint = synthesis_fingerprint
            # created_at is intentionally left unchanged on update

        await self._session.flush()
        return _to_entity(m)
