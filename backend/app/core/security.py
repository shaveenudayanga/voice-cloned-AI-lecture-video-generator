# SPDX-License-Identifier: Apache-2.0
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

# TODO(auth-upgrade): This module currently authenticates via a single server-wide
# API key read from the API_KEY env var. To upgrade to per-user DB-backed keys:
#   1. Implement a UserRepository.get_by_api_key(key) method.
#   2. Replace the body of _verify_api_key with a DB lookup returning a User entity.
#   3. Update the return type annotation here and in deps.py accordingly.
# No endpoint code changes required — only this module and deps.py.

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """Validate the X-API-Key header against the server-wide key."""
    if api_key is None or not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
