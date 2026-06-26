# SPDX-License-Identifier: Apache-2.0
"""
VRAM lifecycle manager for the GPU worker process.

Owns all model references so that adapters never load models directly.
On devices with < 6 GB VRAM (e.g. RTX 3050 Ti 4 GB), F5-TTS and Whisper
cannot coexist; this module handles the eviction protocol automatically.

All state is process-local — each Celery worker fork gets its own copy.
Thread-safe via a single threading.Lock (GPU worker concurrency is 1,
but worker_ready signal and first task may overlap).
"""
import threading
from typing import Any, Literal

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

_lock = threading.Lock()
_tts_model: Any = None        # F5TTS or XTTS instance, or None
_whisper_model: Any = None    # WhisperModel instance, or None
_tts_slot_owner: Literal["f5", "xtts", None] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_vram_free_gb() -> float:
    """Return free VRAM in GB, or -1.0 if CUDA is not available."""
    try:
        import torch

        if not torch.cuda.is_available():
            return -1.0
        free, _ = torch.cuda.mem_get_info()
        return float(free / (1024**3))
    except Exception:
        return -1.0


def load_tts_model() -> Any:
    """Load TTS model into VRAM, evicting Whisper first if budget < 6 GB.

    Returns the model instance (F5TTS or XTTS depending on TTS_ENGINE config).
    Idempotent — if the model is already loaded, returns it immediately.
    """
    global _tts_model, _tts_slot_owner

    with _lock:
        if _tts_model is not None:
            return _tts_model

        if _whisper_model is not None and settings.vram_budget_gb < 6.0:
            _evict_whisper_locked()

        engine = settings.tts_engine
        if engine == "xtts":
            _tts_model = _load_xtts()
            _tts_slot_owner = "xtts"
        else:
            _tts_model = _load_f5()
            _tts_slot_owner = "f5"

        logger.info("model_manager_tts_ready", owner=_tts_slot_owner, vram_free_gb=get_vram_free_gb())
        return _tts_model


def load_whisper_model() -> Any:
    """Load Whisper model, evicting TTS first if VRAM budget < 6 GB.

    Returns the WhisperModel instance.
    Idempotent — if already loaded, returns it immediately.
    """
    global _whisper_model

    with _lock:
        if _whisper_model is not None:
            return _whisper_model

        if _tts_model is not None and settings.vram_budget_gb < 6.0:
            _evict_tts_locked()

        _whisper_model = _load_whisper()
        logger.info("model_manager_whisper_ready", vram_free_gb=get_vram_free_gb())
        return _whisper_model


def unload_current() -> None:
    """Evict all loaded models and free VRAM.  Useful for worker shutdown."""
    with _lock:
        _evict_tts_locked()
        _evict_whisper_locked()


# ---------------------------------------------------------------------------
# Internal helpers — all must be called with _lock held
# ---------------------------------------------------------------------------


def _evict_tts_locked() -> None:
    global _tts_model, _tts_slot_owner

    if _tts_model is None:
        return
    logger.info("model_manager_evicting_tts", owner=_tts_slot_owner)
    _tts_model = None
    _tts_slot_owner = None
    _cuda_empty_cache()
    logger.info("model_manager_tts_evicted")


def _evict_whisper_locked() -> None:
    global _whisper_model

    if _whisper_model is None:
        return
    logger.info("model_manager_evicting_whisper")
    _whisper_model = None
    _cuda_empty_cache()
    logger.info("model_manager_whisper_evicted")


def _cuda_empty_cache() -> None:
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception as exc:
        # CUDA not available on CPU workers — not an error condition
        logger.debug("cuda_empty_cache_unavailable", reason=str(exc))


# ---------------------------------------------------------------------------
# Actual model loaders
# ---------------------------------------------------------------------------


def _load_f5() -> Any:
    import torch
    from f5_tts.api import F5TTS
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # FP16 mandatory on this hardware to fit within 4 GB VRAM (brief hardware constraint #3)
    dtype = torch.float16 if device == "cuda" else torch.float32

    logger.info("model_manager_loading_f5", device=device, dtype=str(dtype))
    model = F5TTS(device=device, dtype=dtype)
    logger.info("model_manager_f5_loaded", vram_free_gb=get_vram_free_gb())
    return model


def _load_xtts() -> Any:
    import torch
    from TTS.api import TTS
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import XttsAudioConfig
    # PyTorch >=2.6 restricts unpickling arbitrary classes. XTTS-v2 checkpoints
    # embed XttsConfig and XttsAudioConfig objects — they must be allowlisted.
    torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig])

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("model_manager_loading_xtts", device=device)
    model = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    logger.info("model_manager_xtts_loaded", vram_free_gb=get_vram_free_gb())
    return model


def _load_whisper() -> Any:
    # On < 6 GB devices Whisper runs on CPU so the GPU stays free for TTS synthesis.
    device = "cpu" if settings.vram_budget_gb < 6.0 else "auto"
    compute_type = "int8" if device == "cpu" else "float16"

    from faster_whisper import WhisperModel
    logger.info("model_manager_loading_whisper", size=settings.whisper_model_size, device=device)
    model = WhisperModel(settings.whisper_model_size, device=device, compute_type=compute_type)
    logger.info("model_manager_whisper_model_loaded", size=settings.whisper_model_size)
    return model
