"""add audio_clips table and voice_profile preview key

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audio_clips",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slide_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("script_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voice_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audio_blob_bucket", sa.String(length=255), nullable=False),
        sa.Column("audio_blob_key", sa.String(length=1024), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("engine_used", sa.String(length=32), nullable=False),
        sa.Column("synthesis_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_audio_clips_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["slide_id"],
            ["slides.id"],
            name=op.f("fk_audio_clips_slide_id_slides"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audio_clips")),
    )
    op.create_index(op.f("ix_audio_clips_project_id"), "audio_clips", ["project_id"], unique=False)
    op.create_index(op.f("ix_audio_clips_slide_id"), "audio_clips", ["slide_id"], unique=False)
    op.create_index(
        op.f("ix_audio_clips_synthesis_fingerprint"),
        "audio_clips",
        ["synthesis_fingerprint"],
        unique=False,
    )

    # Add preview_audio_blob_key to voice_profiles (nullable — set after voice_preview task)
    op.add_column(
        "voice_profiles",
        sa.Column("preview_audio_blob_key", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("voice_profiles", "preview_audio_blob_key")
    op.drop_index(op.f("ix_audio_clips_synthesis_fingerprint"), table_name="audio_clips")
    op.drop_index(op.f("ix_audio_clips_slide_id"), table_name="audio_clips")
    op.drop_index(op.f("ix_audio_clips_project_id"), table_name="audio_clips")
    op.drop_table("audio_clips")
