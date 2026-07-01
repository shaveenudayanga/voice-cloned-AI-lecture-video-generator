# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_version: str = "0.1.0"
    deployment_mode: Literal["web", "desktop"] = "web"
    debug: bool = False

    # Security
    # TODO(auth-upgrade): see docs/known-limitations.md §KL-001
    api_key: str = Field(..., description="Server-wide API key for authentication")

    # CORS — never allow * in production
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # Database
    database_url: str = Field(
        ...,
        description="Async PostgreSQL DSN, e.g. postgresql+asyncpg://user:pass@host/db",
    )

    # Valkey / Redis broker
    valkey_url: str = Field(
        default="redis://valkey:6379/0",
        description="Valkey broker URL (wire-compatible with redis-py)",
    )

    # Object storage (SeaweedFS S3-compatible)
    storage_endpoint_url: str = Field(
        default="http://seaweedfs:8333",
        description="S3-compatible endpoint for SeaweedFS",
    )
    storage_access_key: str = Field(default="", description="S3 access key")
    storage_secret_key: str = Field(default="", description="S3 secret key")
    storage_bucket: str = Field(default="lecturevoice", description="Default bucket")
    storage_region: str = Field(default="us-east-1", description="S3 region (dummy for SeaweedFS)")

    # File upload limits
    max_upload_bytes: int = Field(
        default=50 * 1024 * 1024,
        description="Maximum upload size in bytes (default 50 MB)",
    )
    max_voice_upload_mb: int = Field(
        default=25,
        description="Maximum voice recording upload size in MB (default 25 MB)",
    )

    # LLM
    llm_provider: Literal["gemini", "ollama"] = Field(
        default="gemini",
        description="LLM provider: gemini | ollama",
    )
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key (required when LLM_PROVIDER=gemini)",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model name",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL",
    )
    ollama_model: str = Field(
        default="qwen2.5-vl:7b",
        description="Ollama multimodal model name",
    )

    # TTS
    tts_engine: Literal["f5", "xtts"] = Field(
        default="f5",
        description="TTS engine: f5 | xtts",
    )

    # GPU / VRAM
    vram_budget_gb: float = Field(
        default=12.0,
        description=(
            "VRAM budget in GB. On 4 GB devices, the GPU worker loads F5-TTS OR Whisper, "
            "not both simultaneously. Set to 4.0 on RTX 3050 Ti / similar low-VRAM devices."
        ),
    )

    # Whisper
    whisper_model_size: Literal["tiny", "base", "small", "medium", "large-v3"] = Field(
        default="base",
        description="faster-whisper model size for voice transcription",
    )

    # Video assembly
    ffmpeg_hwaccel: bool = Field(
        default=False,
        description=(
            "Prepend -hwaccel auto to ffmpeg encode commands. "
            "Opt-in only — the default (false) works on any machine without a GPU."
        ),
    )

    # Celery
    celery_task_always_eager: bool = Field(
        default=False,
        description="Run Celery tasks synchronously (useful for testing)",
    )

    # Observability
    otel_exporter: Literal["stdout", "otlp"] = Field(
        default="stdout",
        description="OpenTelemetry trace exporter: stdout | otlp",
    )
    otel_endpoint: str = Field(
        default="",
        description="OTLP exporter endpoint (required when OTEL_EXPORTER=otlp)",
    )

    # Rate limiting
    rate_limit_per_minute: int = Field(
        default=60,
        description="API requests per minute per IP (legacy — kept for backwards compat)",
    )
    rate_limit_default: str = Field(
        default="100/minute",
        description="Default rate limit applied to all endpoints (slowapi format, e.g. '100/minute')",
    )
    rate_limit_upload: str = Field(
        default="10/minute",
        description="Rate limit for file upload endpoints (slides, voices)",
    )
    rate_limit_generate: str = Field(
        default="20/minute",
        description="Rate limit for script generation and audio synthesis endpoints",
    )

    # OTel service name
    otel_service_name: str = Field(
        default="lecturevoice-api",
        description="OpenTelemetry service.name resource attribute",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


settings = Settings()
