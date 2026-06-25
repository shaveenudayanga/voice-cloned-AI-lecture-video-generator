# SPDX-License-Identifier: Apache-2.0
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SlideModel(Base):
    __tablename__ = "slides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Composite blob reference stored as "bucket/key"
    image_blob_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    image_blob_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
