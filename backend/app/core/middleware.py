# SPDX-License-Identifier: Apache-2.0
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

_REQUEST_ID_HEADER = "X-Request-ID"

#: ContextVar that carries the current request ID through the entire call chain.
#: Set by the middleware on every inbound HTTP request.
#: Read by the structlog processor and by tasks via get_request_id().
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the request ID for the current execution context."""
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID for the current execution context (used by Celery task signal)."""
    request_id_var.set(request_id)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Read X-Request-ID from inbound headers (or generate a UUID4), store in ContextVar,
    and echo it back on the response.

    The ContextVar is readable anywhere in the call chain — service layer, task layer,
    structlog processors — without passing the ID as a function argument.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
        set_request_id(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response
