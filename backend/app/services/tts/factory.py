# SPDX-License-Identifier: Apache-2.0
import structlog

from app.core.config import settings
from app.services.tts.interface import TTSEngine

logger = structlog.get_logger(__name__)


def get_tts_engine() -> TTSEngine:
    if settings.tts_engine == "xtts":
        from app.services.tts.xtts_adapter import XTTSEngine

        return XTTSEngine()

    from app.services.tts.f5_adapter import F5TTSEngine

    return F5TTSEngine()


def get_tts_engine_with_fallback() -> TTSEngine:
    """Return F5-TTS, falling back to XTTS-v2 on import error (§7.2)."""
    try:
        from app.services.tts.f5_adapter import F5TTSEngine

        engine = F5TTSEngine()
        engine.warm_up()
        return engine
    except Exception as exc:
        logger.warning("f5tts_unavailable_falling_back_to_xtts", error=str(exc))
        from app.services.tts.xtts_adapter import XTTSEngine

        return XTTSEngine()
