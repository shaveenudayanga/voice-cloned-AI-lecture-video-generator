# SPDX-License-Identifier: Apache-2.0
import structlog

from app.core.config import settings
from app.services.tts.interface import TTSEngine

logger = structlog.get_logger(__name__)


def get_tts_engine() -> TTSEngine:
    """Return the configured TTS engine. Model loading is deferred to first use via model_manager."""
    if settings.tts_engine == "xtts":
        from app.services.tts.xtts_adapter import XTTSAdapter

        return XTTSAdapter()

    from app.services.tts.f5_adapter import F5TTSAdapter

    return F5TTSAdapter()


def get_tts_engine_with_fallback() -> TTSEngine:
    """Return F5-TTS, automatically falling back to XTTS-v2 if F5 fails to import (§7.2)."""
    try:
        from app.services.tts.f5_adapter import F5TTSAdapter

        return F5TTSAdapter()
    except Exception as exc:
        logger.warning("f5tts_unavailable_falling_back_to_xtts", error=str(exc))
        from app.services.tts.xtts_adapter import XTTSAdapter

        return XTTSAdapter()
