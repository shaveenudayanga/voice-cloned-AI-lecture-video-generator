# SPDX-License-Identifier: Apache-2.0
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Job schemas
# ---------------------------------------------------------------------------

JobStatus = Literal["queued", "running", "complete", "failed"]


class JobResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus
    progress_pct: int
    error_message: str | None
    result: dict[str, object] | None


# ---------------------------------------------------------------------------
# Slide upload schema
# ---------------------------------------------------------------------------


class SlideUploadResponse(BaseModel):
    job_id: uuid.UUID
    project_id: uuid.UUID
    status: Literal["queued"]


# ---------------------------------------------------------------------------
# Voice profile schemas
# ---------------------------------------------------------------------------


class VoiceUploadResponse(BaseModel):
    profile_id: uuid.UUID
    job_id: uuid.UUID
    status: Literal["queued"]


class VoiceProfileSummary(BaseModel):
    id: uuid.UUID
    display_name: str
    is_default: bool
    transcript_preview: str
    has_transcript: bool
    created_at: datetime


class VoiceProfileDetail(BaseModel):
    id: uuid.UUID
    display_name: str
    is_default: bool
    style_reference_transcript: str
    transcript_preview: str
    has_transcript: bool
    extra_style_sample: str | None
    tts_engine: str
    created_at: datetime
    updated_at: datetime


class VoicePatchRequest(BaseModel):
    display_name: str | None = None
    extra_style_sample: str | None = None
    is_default: bool | None = None


# ---------------------------------------------------------------------------
# Script schemas
# ---------------------------------------------------------------------------


class ScriptListItem(BaseModel):
    id: uuid.UUID
    slide_id: uuid.UUID
    order_index: int
    text: str
    estimated_reading_seconds: int
    pronunciation_hints: str | None
    version: int
    script_hash: str


class ScriptPatchRequest(BaseModel):
    text: str | None = None
    pronunciation_hints: str | None = None


class ScriptResponse(BaseModel):
    id: uuid.UUID
    slide_id: uuid.UUID
    project_id: uuid.UUID
    text: str
    estimated_reading_seconds: int
    pronunciation_hints: str | None
    version: int
    script_hash: str
    updated_at: datetime


class ScriptGenerateResponse(BaseModel):
    job_ids: list[uuid.UUID]
    slide_count: int
    status: str


# ---------------------------------------------------------------------------
# Voice preview schema
# ---------------------------------------------------------------------------


class VoicePreviewResponse(BaseModel):
    job_id: uuid.UUID
    voice_profile_id: uuid.UUID
    status: Literal["queued"]


# ---------------------------------------------------------------------------
# Audio synthesis schemas
# ---------------------------------------------------------------------------


class AudioSynthesizeResponse(BaseModel):
    job_ids: list[uuid.UUID]
    slide_count: int
    status: Literal["queued"]


class AudioClipItem(BaseModel):
    id: uuid.UUID
    slide_id: uuid.UUID
    order_index: int
    audio_blob_key: str
    duration_seconds: float
    engine_used: str
    synthesis_fingerprint: str


# ---------------------------------------------------------------------------
# Video assembly schemas
# ---------------------------------------------------------------------------


class VideoAssembleResponse(BaseModel):
    job_id: uuid.UUID
    project_id: uuid.UUID
    status: Literal["queued"]


class VideoArtifactResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    video_blob_key: str
    srt_blob_key: str | None
    total_duration_seconds: float
    slide_count: int
    ffmpeg_version: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    title: str


class ProjectPatchRequest(BaseModel):
    voice_profile_id: uuid.UUID | None = None
    wizard_step: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    voice_profile_id: uuid.UUID | None
    wizard_step: str
    created_at: datetime
    updated_at: datetime
