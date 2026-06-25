# SPDX-License-Identifier: Apache-2.0
from celery import Celery

from app.core.config import settings

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
)
