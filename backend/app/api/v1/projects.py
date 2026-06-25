# SPDX-License-Identifier: Apache-2.0
from fastapi import APIRouter

from app.api.deps import AuthDep

router = APIRouter()


@router.get("/projects")
async def list_projects(auth: AuthDep) -> dict[str, object]:
    # Phase 2+ implementation
    return {"projects": []}


@router.post("/projects", status_code=201)
async def create_project(auth: AuthDep) -> dict[str, object]:
    # Phase 2+ implementation
    return {"id": "placeholder", "wizard_step": "upload"}
