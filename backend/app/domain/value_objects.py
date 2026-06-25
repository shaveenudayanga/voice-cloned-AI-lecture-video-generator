# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass


@dataclass(frozen=True)
class BlobKey:
    """Immutable reference to an object in blob storage."""

    bucket: str
    key: str

    def __str__(self) -> str:
        return f"{self.bucket}/{self.key}"


@dataclass(frozen=True)
class AudioFingerprint:
    """Cache key for TTS synthesis idempotency (§7.3 lever 5)."""

    script_hash: str
    voice_profile_id: str
    tts_params_hash: str


@dataclass(frozen=True)
class WizardStep:
    """Valid wizard step names (mirrors frontend route segments)."""

    UPLOAD: str = "upload"
    VOICE: str = "voice"
    SCRIPTS: str = "scripts"
    AUDIO: str = "audio"
    RENDER: str = "render"
    DONE: str = "done"
