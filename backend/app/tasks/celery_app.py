# SPDX-License-Identifier: Apache-2.0
import structlog
from celery import Celery
from celery.signals import worker_ready

from app.core.config import settings

logger = structlog.get_logger(__name__)

celery_app = Celery(
    "lecturevoice",
    broker=settings.valkey_url,
    backend=settings.valkey_url,
    include=[
        "app.tasks.slide_ingestion",
        "app.tasks.voice_ingestion",
        "app.tasks.voice_preview",
        "app.tasks.script_generation",
        "app.tasks.tts_synthesis",
        "app.tasks.video_assembly",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Reliability settings (§7.2)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Test mode support
    task_always_eager=settings.celery_task_always_eager,
    # Route tasks to the correct queue so CPU and GPU workers stay isolated
    task_routes={
        "slide_ingestion": {"queue": "cpu"},
        "voice_ingestion": {"queue": "cpu"},
        "script_generation": {"queue": "cpu"},
        "video_assembly": {"queue": "cpu"},
        "tts_synthesis": {"queue": "gpu"},
        "voice_preview": {"queue": "gpu"},
    },
)


@worker_ready.connect  # type: ignore[untyped-decorator]
def warm_tts_model(sender: object, **kwargs: object) -> None:
    """Pre-load TTS model into VRAM on worker startup (warm worker pattern, §7.3).

    Called for every worker, but model loading is a no-op on CPU workers where
    the GPU deps are not installed (ImportError is caught and logged).
    """
    try:
        from app.services.tts.model_manager import load_tts_model

        load_tts_model()
        logger.info("worker_tts_warm_up_complete")
    except Exception as exc:
        # CPU workers don't have TTS/GPU deps — expected, not an error
        logger.info("worker_tts_warm_up_skipped", reason=str(exc))
