# SPDX-License-Identifier: Apache-2.0
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.middleware import get_request_id
from app.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    LLMGenerationError,
    NotFoundError,
    RateLimitError,
    StorageError,
    TranscriptionError,
    TTSSynthesisError,
    ValidationError,
)

logger = structlog.get_logger(__name__)


def _error_body(exc: Exception, *, request_id: str) -> dict[str, str]:
    return {
        "error": type(exc).__name__,
        "message": str(exc),
        "request_id": request_id,
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        rid = get_request_id()
        logger.error("not_found_error", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(status_code=404, content=_error_body(exc, request_id=rid))

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        rid = get_request_id()
        logger.error("validation_error", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(status_code=422, content=_error_body(exc, request_id=rid))

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        rid = get_request_id()
        logger.error("conflict_error", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(status_code=409, content=_error_body(exc, request_id=rid))

    @app.exception_handler(AuthenticationError)
    async def auth_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        rid = get_request_id()
        logger.error("authentication_error", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(status_code=401, content=_error_body(exc, request_id=rid))

    @app.exception_handler(RateLimitError)
    async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
        rid = get_request_id()
        logger.error("rate_limit_error", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(status_code=429, content=_error_body(exc, request_id=rid))

    @app.exception_handler(StorageError)
    async def storage_handler(request: Request, exc: StorageError) -> JSONResponse:
        rid = get_request_id()
        logger.error("storage_error", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(status_code=502, content=_error_body(exc, request_id=rid))

    @app.exception_handler(LLMGenerationError)
    async def llm_handler(request: Request, exc: LLMGenerationError) -> JSONResponse:
        rid = get_request_id()
        logger.error("llm_generation_error", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(status_code=502, content=_error_body(exc, request_id=rid))

    @app.exception_handler(TTSSynthesisError)
    async def tts_handler(request: Request, exc: TTSSynthesisError) -> JSONResponse:
        rid = get_request_id()
        logger.error("tts_synthesis_error", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(status_code=502, content=_error_body(exc, request_id=rid))

    @app.exception_handler(TranscriptionError)
    async def transcription_handler(request: Request, exc: TranscriptionError) -> JSONResponse:
        rid = get_request_id()
        logger.error("transcription_error", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(status_code=502, content=_error_body(exc, request_id=rid))

    @app.exception_handler(DomainError)
    async def domain_handler(request: Request, exc: DomainError) -> JSONResponse:
        rid = get_request_id()
        logger.error("domain_error", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(status_code=400, content=_error_body(exc, request_id=rid))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = get_request_id()
        logger.critical("unhandled_exception", error=str(exc), request_id=rid, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
                "request_id": rid,
            },
        )
