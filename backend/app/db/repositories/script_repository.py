# SPDX-License-Identifier: Apache-2.0
import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.script import ScriptModel
from app.domain.entities import Script


def compute_script_hash(text: str) -> str:
    """SHA-256 of the narration text — used as the TTS cache-skip fingerprint (§7.3)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _to_entity(m: ScriptModel) -> Script:
    return Script(
        id=m.id,
        slide_id=m.slide_id,
        project_id=m.project_id,
        text=m.text,
        estimated_reading_seconds=m.estimated_reading_seconds,
        pronunciation_hints=m.pronunciation_hints,
        version=m.version,
        script_hash=m.script_hash,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class ScriptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        slide_id: uuid.UUID,
        project_id: uuid.UUID,
        text: str,
        estimated_reading_seconds: int,
        pronunciation_hints: str | None,
    ) -> Script:
        """Create a new script for the slide or overwrite the existing one (idempotent)."""
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(ScriptModel).where(ScriptModel.slide_id == slide_id)
        )
        m = result.scalar_one_or_none()
        script_hash = compute_script_hash(text)

        if m is None:
            m = ScriptModel(
                id=uuid.uuid4(),
                slide_id=slide_id,
                project_id=project_id,
                text=text,
                estimated_reading_seconds=estimated_reading_seconds,
                pronunciation_hints=pronunciation_hints,
                version=1,
                script_hash=script_hash,
                created_at=now,
                updated_at=now,
            )
            self._session.add(m)
        else:
            m.text = text
            m.estimated_reading_seconds = estimated_reading_seconds
            m.pronunciation_hints = pronunciation_hints
            m.script_hash = script_hash
            m.version += 1
            m.updated_at = now

        await self._session.flush()
        return _to_entity(m)

    async def get(self, script_id: uuid.UUID) -> Script | None:
        result = await self._session.execute(
            select(ScriptModel).where(ScriptModel.id == script_id)
        )
        m = result.scalar_one_or_none()
        return _to_entity(m) if m is not None else None

    async def get_by_slide(self, slide_id: uuid.UUID) -> Script | None:
        result = await self._session.execute(
            select(ScriptModel).where(ScriptModel.slide_id == slide_id)
        )
        m = result.scalar_one_or_none()
        return _to_entity(m) if m is not None else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[Script]:
        result = await self._session.execute(
            select(ScriptModel).where(ScriptModel.project_id == project_id)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def update(
        self,
        script_id: uuid.UUID,
        text: str | None = None,
        pronunciation_hints: str | None = None,
    ) -> Script | None:
        """Patch text and/or pronunciation_hints. Recomputes hash and bumps version on text change."""
        result = await self._session.execute(
            select(ScriptModel).where(ScriptModel.id == script_id)
        )
        m = result.scalar_one_or_none()
        if m is None:
            return None

        now = datetime.now(UTC)
        if text is not None and text != m.text:
            m.text = text
            m.script_hash = compute_script_hash(text)
            m.version += 1

        if pronunciation_hints is not None:
            m.pronunciation_hints = pronunciation_hints

        m.updated_at = now
        await self._session.flush()
        return _to_entity(m)
