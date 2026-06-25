# SPDX-License-Identifier: Apache-2.0
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.session import get_session

# Re-export for use in route files
AuthDep = Annotated[str, Depends(verify_api_key)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
