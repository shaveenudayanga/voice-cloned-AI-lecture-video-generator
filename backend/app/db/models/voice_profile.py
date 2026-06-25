# SPDX-License-Identifier: Apache-2.0
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VoiceProfileModel(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    audio_blob_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    audio_blob_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    # Whisper transcript; empty string until voice_ingestion task completes (ADR-0010)
    style_reference_transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extra_style_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    tts_engine: Mapped[str] = mapped_column(String(32), nullable=False, default="f5")
    # JSON-serialised dict of engine-specific params
    tts_params: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
