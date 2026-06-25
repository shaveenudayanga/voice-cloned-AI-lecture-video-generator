# SPDX-License-Identifier: Apache-2.0
from fastapi import APIRouter

from app.api.deps import AuthDep

router = APIRouter()


@router.get("/slides/{slide_id}/script")
async def get_script(slide_id: str, auth: AuthDep) -> dict[str, object]:
    # Phase 4+ implementation
    return {"script": None}
