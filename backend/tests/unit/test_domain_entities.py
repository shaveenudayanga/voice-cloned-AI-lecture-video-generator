# SPDX-License-Identifier: Apache-2.0
import uuid
from datetime import UTC, datetime

from app.domain.entities import Project, VoiceProfile
from app.domain.value_objects import BlobKey


def test_voice_profile_has_user_id() -> None:
    vp = VoiceProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        display_name="Test Voice",
        audio_blob=BlobKey(bucket="lecturevoice", key="users/1/voices/1/ref.wav"),
        style_reference_transcript="Hello, this is a test.",
        extra_style_sample=None,
        tts_engine="f5",
        tts_params={},
        is_default=True,
        created_at=datetime.now(UTC),
    )
    assert vp.user_id is not None
    assert vp.audio_blob.bucket == "lecturevoice"


def test_project_voice_profile_fk() -> None:
    vp_id = uuid.uuid4()
    project = Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Test Lecture",
        voice_profile_id=vp_id,
        wizard_step="upload",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert project.voice_profile_id == vp_id
