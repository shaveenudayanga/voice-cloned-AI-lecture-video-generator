# SPDX-License-Identifier: Apache-2.0
# Import all ORM model modules here so Alembic autogenerate picks them up.
from app.db.models.job import JobModel  # noqa: F401
from app.db.models.project import ProjectModel  # noqa: F401
from app.db.models.script import ScriptModel  # noqa: F401
from app.db.models.slide import SlideModel  # noqa: F401
from app.db.models.voice_profile import VoiceProfileModel  # noqa: F401
