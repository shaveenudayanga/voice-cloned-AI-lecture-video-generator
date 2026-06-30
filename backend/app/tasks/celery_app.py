# SPDX-License-Identifier: Apache-2.0
import time

import structlog
from celery import Celery
from celery.signals import task_postrun, task_prerun, worker_ready

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

# Module-level dict to track task start times for duration histograms
_task_start_times: dict[str, float] = {}


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


@task_prerun.connect  # type: ignore[untyped-decorator]
def on_task_prerun(
    task_id: str,
    task: object,
    args: object,
    kwargs: object,
    **extra: object,
) -> None:
    """Propagate correlation ID from task headers into the ContextVar so all logs
    emitted during this task carry the same request_id as the HTTP request that
    enqueued it.
    """
    from app.core.middleware import set_request_id

    task_name: str = getattr(task, "name", "unknown")
    request_id: str = ""
    task_request = getattr(task, "request", None)
    headers: dict[str, object] = getattr(task_request, "headers", {}) or {}
    rid = headers.get("request_id", "")
    if isinstance(rid, str) and rid:
        request_id = rid
    set_request_id(request_id)
    structlog.contextvars.bind_contextvars(request_id=request_id, task_name=task_name)
    _task_start_times[task_id] = time.perf_counter()
    logger.info("task_started", task_id=task_id, task_name=task_name)


@task_postrun.connect  # type: ignore[untyped-decorator]
def on_task_postrun(
    task_id: str,
    task: object,
    args: object,
    kwargs: object,
    retval: object,
    state: str,
    **extra: object,
) -> None:
    """Record task duration and outcome metrics, then clear correlation context."""
    from app.core.metrics import celery_task_duration_seconds, celery_task_total

    task_name: str = getattr(task, "name", "unknown")
    status = "success" if state == "SUCCESS" else "failure"
    celery_task_total.labels(task_name=task_name, status=status).inc()

    start = _task_start_times.pop(task_id, None)
    if start is not None:
        celery_task_duration_seconds.labels(task_name=task_name).observe(time.perf_counter() - start)

    logger.info("task_finished", task_id=task_id, task_name=task_name, status=status)
    structlog.contextvars.unbind_contextvars("request_id", "task_name")
