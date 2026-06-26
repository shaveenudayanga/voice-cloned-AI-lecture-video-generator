# SPDX-License-Identifier: Apache-2.0
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import audio, health, jobs, projects, scripts, slides, voices
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.telemetry import configure_telemetry
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    prefix = "/api/v1"
    app.include_router(health.router, prefix=prefix, tags=["health"])
    app.include_router(projects.router, prefix=prefix, tags=["projects"])
    app.include_router(slides.router, prefix=prefix, tags=["slides"])
    app.include_router(scripts.router, prefix=prefix, tags=["scripts"])
    app.include_router(voices.router, prefix=prefix, tags=["voices"])
    app.include_router(audio.router, prefix=prefix, tags=["audio"])
    app.include_router(jobs.router, prefix=prefix, tags=["jobs"])

    return app


app = create_app()
