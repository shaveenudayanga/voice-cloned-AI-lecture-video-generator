# SPDX-License-Identifier: Apache-2.0
from fastapi import APIRouter

from app.api.deps import AuthDep

router = APIRouter()


@router.get("/voices")
async def list_voice_profiles(auth: AuthDep) -> dict[str, object]:
    # Phase 3+ implementation
    return {"voices": []}
