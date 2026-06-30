# SPDX-License-Identifier: Apache-2.0


class DomainError(Exception):
    """Base class for all domain-layer errors."""


class NotFoundError(DomainError):
    """Raised when a requested entity does not exist."""


class ValidationError(DomainError):
    """Raised when domain invariants are violated."""


class ConflictError(DomainError):
    """Raised when an operation conflicts with existing state (e.g. duplicate, reference block)."""


class AuthenticationError(DomainError):
    """Raised when authentication credentials are missing or invalid."""


class RateLimitError(DomainError):
    """Raised when a caller exceeds the configured rate limit."""


class StorageError(DomainError):
    """Raised when blob storage operations fail."""


class LLMGenerationError(DomainError):
    """Raised when LLM script generation fails or returns invalid output."""


class TTSSynthesisError(DomainError):
    """Raised when TTS synthesis fails after exhausting retries."""


class TranscriptionError(DomainError):
    """Raised when Whisper transcription fails."""


# ---------------------------------------------------------------------------
# Legacy aliases kept so existing task code that raises TTSError /
# ScriptGenerationError / VideoAssemblyError does not need to be rewritten.
# ---------------------------------------------------------------------------


class TTSError(TTSSynthesisError):
    """Alias for TTSSynthesisError (legacy name used in task code)."""


class ScriptGenerationError(LLMGenerationError):
    """Alias for LLMGenerationError (legacy name used in task code)."""


class VideoAssemblyError(DomainError):
    """Raised when ffmpeg video assembly fails."""
