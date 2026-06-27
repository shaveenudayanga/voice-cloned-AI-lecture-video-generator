# SPDX-License-Identifier: Apache-2.0
"""Blob proxy — streams SeaweedFS objects to the browser without exposing the
internal storage address. Auth-gated so only authenticated frontend clients
can fetch voice recordings, slide images, audio clips, and video artifacts."""

from pathlib import PurePosixPath

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.api.deps import AuthDep
from app.core.config import settings
from app.services.storage.factory import get_blob_store

router = APIRouter()
logger = structlog.get_logger(__name__)

_EXT_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".wav": "audio/wav",
    ".webm": "audio/webm",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".srt": "text/plain",
    ".pdf": "application/pdf",
}


@router.get("/blobs/{blob_key:path}")
async def get_blob(blob_key: str, auth: AuthDep) -> Response:
    """Proxy a blob from SeaweedFS.

    The blob_key is a path (may contain '/'), e.g.
    projects/123/audio/slide-1.wav — the frontend must NOT percent-encode
    slashes; the FastAPI :path converter preserves them verbatim.

    Never exposes the internal SeaweedFS address to the browser.
    """
    store = get_blob_store()
    try:
        data = await store.get(bucket=settings.storage_bucket, key=blob_key)
    except Exception as exc:
        logger.info("blob_proxy_not_found", blob_key=blob_key, error=str(exc))
        raise HTTPException(status_code=404, detail="Blob not found") from exc

    ext = PurePosixPath(blob_key).suffix.lower()
    content_type = _EXT_MIME.get(ext, "application/octet-stream")

    logger.debug("blob_proxy_served", blob_key=blob_key, size=len(data))
    return Response(content=data, media_type=content_type)
