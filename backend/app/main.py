# SPDX-License-Identifier: Apache-2.0
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import audio, blobs, health, jobs, projects, scripts, slides, video, voices
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.metrics import PrometheusMetricsMiddleware
from app.core.middleware import CorrelationIDMiddleware
from app.core.rate_limit import limiter
from app.core.telemetry import configure_telemetry, instrument_app
from app.db.session import close_engine, init_engine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    configure_telemetry()
    await init_engine()
    logger.info("lecturevoice_startup", version=settings.app_version)
    yield
    await close_engine()
    logger.info("lecturevoice_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="LectureVoice API",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Instrument OTel BEFORE routers are registered so all routes are covered
    instrument_app(app)

    # Attach the slowapi limiter to the app state
    app.state.limiter = limiter

    # Middleware registration order matters: outermost first.
    # CorrelationID sets the request_id before anything else runs.
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(PrometheusMetricsMiddleware)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # slowapi raises RateLimitExceeded; map it to a 429 JSON response
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )

    register_exception_handlers(app)

    prefix = "/api/v1"
    app.include_router(health.router, prefix=prefix, tags=["health"])
    app.include_router(projects.router, prefix=prefix, tags=["projects"])
    app.include_router(slides.router, prefix=prefix, tags=["slides"])
    app.include_router(scripts.router, prefix=prefix, tags=["scripts"])
    app.include_router(voices.router, prefix=prefix, tags=["voices"])
    app.include_router(audio.router, prefix=prefix, tags=["audio"])
    app.include_router(video.router, prefix=prefix, tags=["video"])
    app.include_router(jobs.router, prefix=prefix, tags=["jobs"])
    app.include_router(blobs.router, prefix=prefix, tags=["blobs"])

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        """Prometheus text-format metrics endpoint. No auth required (standard convention)."""
        return PlainTextResponse(
            generate_latest().decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


app = create_app()
