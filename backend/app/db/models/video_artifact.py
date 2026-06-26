# SPDX-License-Identifier: Apache-2.0
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VideoArtifactModel(Base):
    __tablename__ = "video_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, unique=True)
    video_blob_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    video_blob_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    srt_blob_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    srt_blob_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    total_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    slide_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ffmpeg_version: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
