"""add voice_profiles and projects tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voice_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("audio_blob_bucket", sa.String(length=255), nullable=False),
        sa.Column("audio_blob_key", sa.String(length=1024), nullable=False),
        sa.Column("style_reference_transcript", sa.Text(), nullable=False, server_default=""),
        sa.Column("extra_style_sample", sa.Text(), nullable=True),
        sa.Column("tts_engine", sa.String(length=32), nullable=False, server_default="f5"),
        sa.Column("tts_params", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voice_profiles")),
    )
    op.create_index(op.f("ix_voice_profiles_user_id"), "voice_profiles", ["user_id"], unique=False)

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("voice_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("wizard_step", sa.String(length=32), nullable=False, server_default="upload"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["voice_profile_id"],
            ["voice_profiles.id"],
            name=op.f("fk_projects_voice_profile_id_voice_profiles"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(op.f("ix_projects_user_id"), "projects", ["user_id"], unique=False)

    # Add FK from slides.project_id → projects.id (slides was created without FK in 0001)
    op.create_foreign_key(
        op.f("fk_slides_project_id_projects"),
        "slides",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_slides_project_id_projects"), "slides", type_="foreignkey")
    op.drop_index(op.f("ix_projects_user_id"), table_name="projects")
    op.drop_table("projects")
    op.drop_index(op.f("ix_voice_profiles_user_id"), table_name="voice_profiles")
    op.drop_table("voice_profiles")
