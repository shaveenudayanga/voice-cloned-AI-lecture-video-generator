# SPDX-License-Identifier: Apache-2.0
"""Prometheus metrics definitions for LectureVoice.

All metrics are module-level singletons. Import and increment from anywhere in the
service layer or task layer — prometheus-client is process-global.
"""

import time

from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# HTTP metrics
# ---------------------------------------------------------------------------

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests handled",
    ["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ---------------------------------------------------------------------------
# Celery task metrics
# ---------------------------------------------------------------------------

celery_task_total = Counter(
    "celery_task_total",
    "Celery task executions",
    ["task_name", "status"],  # status: success | failure
)

celery_task_duration_seconds = Histogram(
    "celery_task_duration_seconds",
    "Celery task wall-clock duration in seconds",
    ["task_name"],
    buckets=(0.1, 0.5, 1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0),
)

celery_queue_depth = Gauge(
    "celery_queue_depth",
    "Approximate number of messages in a Celery queue",
    ["queue_name"],
)

# ---------------------------------------------------------------------------
# TTS cache metrics
# ---------------------------------------------------------------------------

tts_synthesis_cache_hits_total = Counter(
    "tts_synthesis_cache_hits_total",
    "TTS synthesis tasks skipped because the fingerprint matched an existing AudioClip",
)

tts_synthesis_cache_misses_total = Counter(
    "tts_synthesis_cache_misses_total",
    "TTS synthesis tasks that required calling the TTS engine (cache miss)",
)

# ---------------------------------------------------------------------------
# LLM metrics
# ---------------------------------------------------------------------------

llm_script_generation_total = Counter(
    "llm_script_generation_total",
    "LLM script generation calls",
    ["provider", "status"],  # status: success | failure
)


# ---------------------------------------------------------------------------
# HTTP metrics middleware
# ---------------------------------------------------------------------------


def _normalize_path(path: str) -> str:
    """Replace UUID-shaped path segments with {id} to avoid high cardinality."""
    import re

    return re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "{id}",
        path,
        flags=re.IGNORECASE,
    )


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Record http_requests_total and http_request_duration_seconds for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method
        path = _normalize_path(request.url.path)
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        status = str(response.status_code)
        http_requests_total.labels(method=method, path=path, status_code=status).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)
        return response
