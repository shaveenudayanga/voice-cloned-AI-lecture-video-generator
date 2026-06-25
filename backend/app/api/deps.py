# SPDX-License-Identifier: Apache-2.0
import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.session import get_session

# Re-export for use in route files
AuthDep = Annotated[str, Depends(verify_api_key)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_user_id(api_key: str = Depends(verify_api_key)) -> uuid.UUID:
    """Derive a stable user UUID from the current API key.

    Phase 3 placeholder until per-user DB-backed auth replaces the server-wide key.
    When core/security.py is upgraded to return a User entity, return user.id here.
    The uuid5 mapping ensures the same key always resolves to the same user_id.
    """
    return uuid.uuid5(uuid.NAMESPACE_OID, api_key)


UserIdDep = Annotated[uuid.UUID, Depends(get_user_id)]
