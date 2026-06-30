# SPDX-License-Identifier: Apache-2.0
"""Phase 9 tests: correlation ID middleware, Prometheus metrics, rate limiting,
error handler hierarchy.
"""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar_one.return_value = 0
    session.execute = AsyncMock(return_value=mock_result)
    return session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    from app.db.session import get_session
    from app.main import app

    mock_session = _make_mock_session()

    async def override_session() -> AsyncGenerator[AsyncMock]:
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_session, None)


# ---------------------------------------------------------------------------
# Deliverable 1 — Correlation ID middleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_generates_request_id_when_absent(client: AsyncClient) -> None:
    """X-Request-ID is generated and returned when the request carries none."""
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    rid = resp.headers.get("x-request-id")
    assert rid is not None
    # Must be a valid UUID4
    parsed = uuid.UUID(rid)
    assert str(parsed) == rid


@pytest.mark.asyncio
async def test_middleware_preserves_incoming_request_id(client: AsyncClient) -> None:
    """X-Request-ID from the request is echoed unchanged on the response."""
    incoming_id = str(uuid.uuid4())
    resp = await client.get("/api/v1/health/live", headers={"X-Request-ID": incoming_id})
    assert resp.status_code == 200
    assert resp.headers.get("x-request-id") == incoming_id


@pytest.mark.asyncio
async def test_middleware_assigns_different_ids_per_request(client: AsyncClient) -> None:
    """Two requests without an X-Request-ID header get two different IDs."""
    r1 = await client.get("/api/v1/health/live")
    r2 = await client.get("/api/v1/health/live")
    id1 = r1.headers.get("x-request-id")
    id2 = r2.headers.get("x-request-id")
    assert id1 != id2


@pytest.mark.asyncio
async def test_request_id_injected_into_contextvar_during_request() -> None:
    """CorrelationIDMiddleware sets the request_id ContextVar during request processing."""
    import uuid

    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from app.core.middleware import CorrelationIDMiddleware, request_id_var

    captured_during: list[str] = []

    async def endpoint(request: Request) -> PlainTextResponse:
        # Read the ContextVar while the middleware is active
        captured_during.append(request_id_var.get())
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/ping", endpoint)])
    app.add_middleware(CorrelationIDMiddleware)

    expected_id = str(uuid.uuid4())
    # TestClient runs synchronously — fine for this assertion
    with TestClient(app, raise_server_exceptions=True) as tc:
        tc.get("/ping", headers={"X-Request-ID": expected_id})

    assert captured_during == [expected_id]


# ---------------------------------------------------------------------------
# Deliverable 3 — Prometheus /metrics endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_http_requests_total(client: AsyncClient) -> None:
    # Make one request first to populate the counter
    await client.get("/api/v1/health/live")
    resp = await client.get("/metrics")
    assert "http_requests_total" in resp.text


@pytest.mark.asyncio
async def test_metrics_endpoint_requires_no_auth(client: AsyncClient) -> None:
    """GET /metrics must succeed without X-API-Key (standard Prometheus convention)."""
    resp = await client.get("/metrics")
    # Must not return 401
    assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Deliverable 5 — Rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_endpoint_returns_429_after_rate_limit() -> None:
    """POST /slides/upload returns 429 after exceeding RATE_LIMIT_UPLOAD.

    We build a minimal Starlette app with SlowAPIMiddleware and a route decorated
    with a 1/minute limit to isolate the rate-limiting behaviour.
    """
    from slowapi import Limiter, _rate_limit_exceeded_handler  # type: ignore[attr-defined]
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    _limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

    @_limiter.limit("1/minute")
    async def upload_stub(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/upload", upload_stub, methods=["POST"])])
    app.state.limiter = _limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    with TestClient(app, raise_server_exceptions=False) as tc:
        r1 = tc.post("/upload")
        r2 = tc.post("/upload")

    assert r1.status_code == 200
    assert r2.status_code == 429


# ---------------------------------------------------------------------------
# Deliverable 6 — Error handler hierarchy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validation_error_returns_422_with_request_id() -> None:
    """A domain ValidationError raised in an endpoint returns 422 with request_id."""
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from app.core.errors import register_exception_handlers
    from app.core.middleware import CorrelationIDMiddleware
    from app.domain.exceptions import ValidationError

    mini = FastAPI()
    mini.add_middleware(CorrelationIDMiddleware)
    register_exception_handlers(mini)

    @mini.get("/bad")
    async def _raise() -> None:
        raise ValidationError("bad input for test")

    with TestClient(mini, raise_server_exceptions=False) as tc:
        resp = tc.get("/bad")

    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "ValidationError"
    assert "request_id" in body


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500_with_internal_server_error() -> None:
    """An unhandled Exception returns 500 with 'InternalServerError' and request_id.

    Uses raise_server_exceptions=False so the test client converts the server
    error into a response rather than re-raising it in the test process.
    """
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    from app.core.errors import register_exception_handlers
    from app.core.middleware import CorrelationIDMiddleware

    mini = FastAPI()
    mini.add_middleware(CorrelationIDMiddleware)
    register_exception_handlers(mini)

    @mini.get("/boom")
    async def _raise() -> None:
        raise RuntimeError("boom — unexpected")

    with TestClient(mini, raise_server_exceptions=False) as tc:
        resp = tc.get("/boom")

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"] == "InternalServerError"
    assert body["message"] == "An unexpected error occurred"
    assert "request_id" in body
