# SPDX-License-Identifier: Apache-2.0
import uuid

import structlog
from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

from app.api.deps import AuthDep, SessionDep, UserIdDep
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.repositories.job_repository import JobRepository
from app.db.repositories.project_repository import ProjectRepository
from app.db.repositories.voice_profile_repository import VoiceProfileRepository
from app.domain.entities import VoiceProfile
from app.domain.value_objects import BlobKey
from app.schemas import (
    VoicePatchRequest,
    VoicePreviewResponse,
    VoiceProfileDetail,
    VoiceProfileSummary,
    VoiceUploadResponse,
)
from app.services.audio.mime import sniff_audio_mime
from app.services.storage.factory import get_blob_store
from app.tasks.voice_ingestion import ingest_voice
from app.tasks.voice_preview import synthesize_preview

router = APIRouter()
logger = structlog.get_logger(__name__)

_MIME_SNIFF_BYTES = 12


def _to_summary(p: VoiceProfile) -> VoiceProfileSummary:
    return VoiceProfileSummary(
        id=p.id,
        display_name=p.display_name,
        is_default=p.is_default,
        transcript_preview=p.style_reference_transcript[:100],
        has_transcript=bool(p.style_reference_transcript),
        created_at=p.created_at,
    )


def _to_detail(p: VoiceProfile) -> VoiceProfileDetail:
    return VoiceProfileDetail(
        id=p.id,
        display_name=p.display_name,
        is_default=p.is_default,
        style_reference_transcript=p.style_reference_transcript,
        transcript_preview=p.style_reference_transcript[:100],
        has_transcript=bool(p.style_reference_transcript),
        extra_style_sample=p.extra_style_sample,
        tts_engine=p.tts_engine,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.post("/voices", status_code=202, response_model=VoiceUploadResponse)
@limiter.limit(settings.rate_limit_upload)
async def create_voice_profile(
    request: Request,
    file: UploadFile,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
    display_name: str = Form(...),
) -> VoiceUploadResponse:
    """Accept a voice recording, store it, and enqueue transcription."""
    raw = await file.read()

    if len(raw) > settings.max_voice_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {settings.max_voice_upload_mb} MB",
        )

    declared = file.content_type or ""
    mime = sniff_audio_mime(raw[:_MIME_SNIFF_BYTES], declared)
    if mime is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a WAV, MP3, OGG, MP4, or WebM audio file.",
        )

    voice_repo = VoiceProfileRepository(session)
    job_repo = JobRepository(session)

    # Pre-allocate the profile UUID so the blob key and DB row share the same ID
    profile_id = uuid.uuid4()
    blob_key = f"users/{user_id}/voices/{profile_id}.wav"

    store = get_blob_store()
    await store.ensure_bucket(settings.storage_bucket)
    await store.put(
        bucket=settings.storage_bucket,
        key=blob_key,
        data=raw,
        content_type=mime,
    )
    logger.info("voice_upload_stored", user_id=str(user_id), profile_id=str(profile_id), size=len(raw))

    # First profile for this user is automatically the default
    count = await voice_repo.count_by_user(user_id)
    is_first = count == 0

    profile = await voice_repo.create(
        profile_id=profile_id,
        user_id=user_id,
        display_name=display_name,
        audio_blob=BlobKey(bucket=settings.storage_bucket, key=blob_key),
        tts_engine=settings.tts_engine,
        tts_params={},
        is_default=is_first,
    )

    ingest_job = await job_repo.create(task_name="voice_ingestion", related_entity_id=profile.id)
    preview_job = await job_repo.create(task_name="voice_preview", related_entity_id=profile.id)
    await session.commit()

    ingest_voice.delay(
        voice_profile_id=str(profile.id),
        blob_key=blob_key,
        job_id=str(ingest_job.id),
    )
    synthesize_preview.delay(
        voice_profile_id=str(profile.id),
        user_id=str(user_id),
        job_id=str(preview_job.id),
    )

    return VoiceUploadResponse(profile_id=profile.id, job_id=ingest_job.id, status="queued")


@router.get("/voices", response_model=list[VoiceProfileSummary])
async def list_voice_profiles(
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> list[VoiceProfileSummary]:
    """List all VoiceProfiles for the current user."""
    voice_repo = VoiceProfileRepository(session)
    profiles = await voice_repo.list_by_user(user_id)
    return [_to_summary(p) for p in profiles]


@router.get("/voices/{profile_id}", response_model=VoiceProfileDetail)
async def get_voice_profile(
    profile_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> VoiceProfileDetail:
    """Retrieve full detail for a single VoiceProfile."""
    voice_repo = VoiceProfileRepository(session)
    profile = await voice_repo.get(profile_id)
    if profile is None or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="VoiceProfile not found")
    return _to_detail(profile)


@router.patch("/voices/{profile_id}", response_model=VoiceProfileDetail)
async def patch_voice_profile(
    profile_id: uuid.UUID,
    body: VoicePatchRequest,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> VoiceProfileDetail:
    """Update display_name, extra_style_sample, or is_default."""
    voice_repo = VoiceProfileRepository(session)
    profile = await voice_repo.get(profile_id)
    if profile is None or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="VoiceProfile not found")

    if body.is_default:
        # Ensure at most one default per user
        await voice_repo.unset_default_for_user(user_id)

    updated = await voice_repo.update(
        profile_id=profile_id,
        display_name=body.display_name,
        extra_style_sample=body.extra_style_sample,
        is_default=body.is_default,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="VoiceProfile not found")
    await session.commit()
    return _to_detail(updated)


@router.delete("/voices/{profile_id}", status_code=204)
async def delete_voice_profile(
    profile_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> None:
    """Delete a VoiceProfile and its stored audio. Returns 409 if any project references it."""
    voice_repo = VoiceProfileRepository(session)
    project_repo = ProjectRepository(session)

    profile = await voice_repo.get(profile_id)
    if profile is None or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="VoiceProfile not found")

    referencing = await project_repo.list_by_voice_profile(profile_id)
    if referencing:
        names = ", ".join(p.title for p in referencing)
        raise HTTPException(
            status_code=409,
            detail=f"VoiceProfile is still referenced by: {names}. Remove the voice from those projects first.",
        )

    store = get_blob_store()
    try:
        await store.delete(bucket=profile.audio_blob.bucket, key=profile.audio_blob.key)
    except Exception:
        logger.warning("voice_delete_blob_failed", profile_id=str(profile_id))

    await voice_repo.delete(profile_id)
    await session.commit()


@router.post("/voices/{profile_id}/preview", status_code=202, response_model=VoicePreviewResponse)
async def trigger_voice_preview(
    profile_id: uuid.UUID,
    auth: AuthDep,
    user_id: UserIdDep,
    session: SessionDep,
) -> VoicePreviewResponse:
    """Synthesize the one-sentence clone-quality test for a VoiceProfile.

    Can be called after upload (auto-triggered) or manually when the user wants
    to re-verify their clone before starting a new lecture.
    """
    voice_repo = VoiceProfileRepository(session)
    job_repo = JobRepository(session)

    profile = await voice_repo.get(profile_id)
    if profile is None or profile.user_id != user_id:
        raise HTTPException(status_code=404, detail="VoiceProfile not found")

    job = await job_repo.create(task_name="voice_preview", related_entity_id=profile.id)
    await session.commit()

    synthesize_preview.delay(
        voice_profile_id=str(profile.id),
        user_id=str(user_id),
        job_id=str(job.id),
    )

    return VoicePreviewResponse(
        job_id=job.id,
        voice_profile_id=profile.id,
        status="queued",
    )
