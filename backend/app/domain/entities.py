# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.domain.value_objects import BlobKey

WizardStepLiteral = Literal["upload", "voice", "scripts", "audio", "render", "done"]
JobStatusLiteral = Literal["pending", "running", "success", "failed", "retrying"]


@dataclass
class User:
    id: uuid.UUID
    email: str
    api_key_hash: str
    created_at: datetime


@dataclass
class VoiceProfile:
    """User-owned, reusable across projects. See ADR-0009."""

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    # Blob key for the raw reference audio clip
    audio_blob: BlobKey
    # Whisper transcript of the recording — fed to the LLM as style reference (ADR-0010)
    style_reference_transcript: str
    # Optional additional style sample pasted by the user
    extra_style_sample: str | None
    tts_engine: Literal["f5", "xtts"]
    tts_params: dict[str, object]
    is_default: bool
    created_at: datetime
    updated_at: datetime
    # Blob key of the one-sentence clone-quality preview synthesized after recording (Phase 5)
    preview_audio_blob_key: str | None = None


@dataclass
class Project:
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    # Explicit FK to the active VoiceProfile at synthesis time (§3.6)
    voice_profile_id: uuid.UUID | None
    # Persisted wizard step so the user can leave and resume (§8 Phase 7)
    wizard_step: WizardStepLiteral
    created_at: datetime
    updated_at: datetime


@dataclass
class Slide:
    id: uuid.UUID
    project_id: uuid.UUID
    order_index: int
    image_blob: BlobKey
    extracted_text: str
    created_at: datetime


@dataclass
class Script:
    id: uuid.UUID
    slide_id: uuid.UUID
    project_id: uuid.UUID
    text: str
    estimated_reading_seconds: int
    pronunciation_hints: str | None
    version: int
    # SHA-256 of text; used for TTS cache-skip fingerprint (§7.3 lever 5)
    script_hash: str
    created_at: datetime
    updated_at: datetime


@dataclass
class AudioClip:
    """Synthesized audio for one slide script. Fingerprint drives cache-skip (§7.3 lever 5)."""

    id: uuid.UUID
    project_id: uuid.UUID
    slide_id: uuid.UUID
    script_id: uuid.UUID
    voice_profile_id: uuid.UUID
    audio_blob: BlobKey
    duration_seconds: float
    engine_used: str
    # SHA-256 of (script_hash + voice_profile_id + tts_engine + tts_params) — cache-skip key
    synthesis_fingerprint: str
    created_at: datetime


@dataclass
class VideoArtifact:
    id: uuid.UUID
    project_id: uuid.UUID
    video_blob: BlobKey
    srt_blob: BlobKey | None
    total_duration_s: float
    created_at: datetime


@dataclass
class Job:
    id: uuid.UUID
    task_name: str
    status: JobStatusLiteral
    progress_pct: int
    result_payload: dict[str, object] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    related_entity_id: uuid.UUID | None = field(default=None)
