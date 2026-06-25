# SPDX-License-Identifier: Apache-2.0


class DomainError(Exception):
    """Base class for all domain-layer errors."""


class NotFoundError(DomainError):
    """Raised when a requested entity does not exist."""


class ValidationError(DomainError):
    """Raised when domain invariants are violated."""


class StorageError(DomainError):
    """Raised when blob storage operations fail."""


class TTSError(DomainError):
    """Raised when TTS synthesis fails."""


class TranscriptionError(DomainError):
    """Raised when Whisper transcription fails."""


class ScriptGenerationError(DomainError):
    """Raised when LLM script generation fails or returns invalid output."""


class VideoAssemblyError(DomainError):
    """Raised when ffmpeg video assembly fails."""
