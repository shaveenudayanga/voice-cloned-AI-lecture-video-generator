# SPDX-License-Identifier: Apache-2.0
import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import settings

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Process is up. No dependency checks."""
    return {"status": "ok", "version": settings.app_version}


@router.get("/health/ready")
async def readiness(session: SessionDep) -> dict[str, object]:
    """All critical dependencies are reachable."""
    checks: dict[str, str] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        logger.warning("health_check_postgres_failed", error=str(exc))
        checks["postgres"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}
