# SPDX-License-Identifier: Apache-2.0
import httpx
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import settings

router = APIRouter()
logger = structlog.get_logger(__name__)

_PING_TIMEOUT = 2.0  # seconds per dependency health check


async def _ping_valkey(url: str) -> str:
    """PING the Valkey broker; return 'ok' or 'error: <msg>'."""
    r = aioredis.from_url(  # type: ignore[no-untyped-call]
        url, socket_timeout=_PING_TIMEOUT, socket_connect_timeout=_PING_TIMEOUT
    )
    try:
        await r.ping()
        return "ok"
    except Exception as exc:
        return f"error: {exc}"
    finally:
        await r.aclose()


async def _ping_seaweedfs(endpoint: str) -> str:
    """HEAD the SeaweedFS S3 endpoint; return 'ok' or 'error: <msg>'.

    Any HTTP response (even 403/404) means the server is reachable.
    A connection error or 5xx means it is not.
    """
    try:
        async with httpx.AsyncClient(timeout=_PING_TIMEOUT) as client:
            resp = await client.get(endpoint)
            if resp.status_code < 500:
                return "ok"
            return f"error: HTTP {resp.status_code}"
    except Exception as exc:
        return f"error: {exc}"


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Process is up. No dependency checks."""
    return {"status": "ok", "version": settings.app_version}


@router.get("/health/ready")
async def readiness(session: SessionDep) -> dict[str, object]:
    """All critical dependencies are reachable.

    Returns 200 even when a dependency is degraded so callers can see
    *which* check failed rather than receiving an opaque 500.
    """
    checks: dict[str, str] = {}

    # --- Postgres ---
    try:
        await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        logger.warning("health_check_postgres_failed", error=str(exc))
        checks["postgres"] = f"error: {exc}"

    # --- Valkey ---
    checks["valkey"] = await _ping_valkey(settings.valkey_url)
    if checks["valkey"] != "ok":
        logger.warning("health_check_valkey_failed", result=checks["valkey"])

    # --- SeaweedFS ---
    checks["seaweedfs"] = await _ping_seaweedfs(settings.storage_endpoint_url)
    if checks["seaweedfs"] != "ok":
        logger.warning("health_check_seaweedfs_failed", result=checks["seaweedfs"])

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}
