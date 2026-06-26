# SPDX-License-Identifier: Apache-2.0
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.video_artifact import VideoArtifactModel
from app.domain.entities import VideoArtifact
from app.domain.value_objects import BlobKey


def _to_entity(m: VideoArtifactModel) -> VideoArtifact:
    srt_blob: BlobKey | None = None
    if m.srt_blob_bucket is not None and m.srt_blob_key is not None:
        srt_blob = BlobKey(bucket=m.srt_blob_bucket, key=m.srt_blob_key)
    return VideoArtifact(
        id=m.id,
        project_id=m.project_id,
        video_blob=BlobKey(bucket=m.video_blob_bucket, key=m.video_blob_key),
        srt_blob=srt_blob,
        total_duration_seconds=m.total_duration_seconds,
        slide_count=m.slide_count,
        ffmpeg_version=m.ffmpeg_version,
        created_at=m.created_at,
    )


class VideoArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_project(self, project_id: uuid.UUID) -> VideoArtifact | None:
        result = await self._session.execute(
            select(VideoArtifactModel).where(VideoArtifactModel.project_id == project_id)
        )
        m = result.scalar_one_or_none()
        return _to_entity(m) if m is not None else None

    async def upsert(
        self,
        project_id: uuid.UUID,
        video_blob: BlobKey,
        srt_blob: BlobKey | None,
        total_duration_seconds: float,
        slide_count: int,
        ffmpeg_version: str,
    ) -> VideoArtifact:
        """Insert or overwrite the VideoArtifact for this project (idempotent)."""
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(VideoArtifactModel).where(VideoArtifactModel.project_id == project_id)
        )
        m = result.scalar_one_or_none()

        if m is None:
            m = VideoArtifactModel(
                id=uuid.uuid4(),
                project_id=project_id,
                video_blob_bucket=video_blob.bucket,
                video_blob_key=video_blob.key,
                srt_blob_bucket=srt_blob.bucket if srt_blob else None,
                srt_blob_key=srt_blob.key if srt_blob else None,
                total_duration_seconds=total_duration_seconds,
                slide_count=slide_count,
                ffmpeg_version=ffmpeg_version,
                created_at=now,
            )
            self._session.add(m)
        else:
            m.video_blob_bucket = video_blob.bucket
            m.video_blob_key = video_blob.key
            m.srt_blob_bucket = srt_blob.bucket if srt_blob else None
            m.srt_blob_key = srt_blob.key if srt_blob else None
            m.total_duration_seconds = total_duration_seconds
            m.slide_count = slide_count
            m.ffmpeg_version = ffmpeg_version
            # created_at intentionally left unchanged on update

        await self._session.flush()
        return _to_entity(m)
