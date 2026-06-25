# SPDX-License-Identifier: Apache-2.0
import uuid
from typing import Literal

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Job schemas
# ---------------------------------------------------------------------------

JobStatus = Literal["queued", "running", "complete", "failed"]


class JobResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus
    progress_pct: int
    error_message: str | None
    result: dict[str, object] | None


# ---------------------------------------------------------------------------
# Slide upload schema
# ---------------------------------------------------------------------------


class SlideUploadResponse(BaseModel):
    job_id: uuid.UUID
    project_id: uuid.UUID
    status: Literal["queued"]
