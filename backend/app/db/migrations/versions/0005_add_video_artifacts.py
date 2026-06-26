"""add video_artifacts table

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_blob_bucket", sa.String(length=255), nullable=False),
        sa.Column("video_blob_key", sa.String(length=1024), nullable=False),
        sa.Column("srt_blob_bucket", sa.String(length=255), nullable=True),
        sa.Column("srt_blob_key", sa.String(length=1024), nullable=True),
        sa.Column("total_duration_seconds", sa.Float(), nullable=False),
        sa.Column("slide_count", sa.Integer(), nullable=False),
        sa.Column("ffmpeg_version", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_video_artifacts_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_video_artifacts")),
        sa.UniqueConstraint("project_id", name=op.f("uq_video_artifacts_project_id")),
    )
    op.create_index(
        op.f("ix_video_artifacts_project_id"),
        "video_artifacts",
        ["project_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_video_artifacts_project_id"), table_name="video_artifacts")
    op.drop_table("video_artifacts")
