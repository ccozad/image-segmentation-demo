from datetime import datetime
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..config import Settings, get_settings
from ..db import get_session
from ..models import Job, JobStatus
from ..schemas import JobCreated, JobRead
from ..storage import Storage, get_storage

router = APIRouter()
log = structlog.get_logger()

# Accepted upload content types -> file extension used for the object key.
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


async def _to_read(job: Job, storage: Storage, settings: Settings) -> JobRead:
    raw_url = await run_in_threadpool(
        storage.presigned_get, settings.raw_bucket, job.raw_key, settings.presigned_url_ttl
    )
    annotated_url = None
    if job.annotated_key:
        annotated_url = await run_in_threadpool(
            storage.presigned_get,
            settings.annotated_bucket,
            job.annotated_key,
            settings.presigned_url_ttl,
        )
    return JobRead(
        id=job.id,
        prompt=job.prompt,
        status=job.status,
        mask_count=job.mask_count,
        processing_ms=job.processing_ms,
        uploaded_at=job.uploaded_at,
        completed_at=job.completed_at,
        raw_url=raw_url,
        annotated_url=annotated_url,
    )


@router.post("/images", status_code=201, response_model=JobCreated)
async def create_image(
    file: UploadFile = File(...),
    prompt: str = Form(...),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> JobCreated:
    ext = ALLOWED_CONTENT_TYPES.get(file.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=415,
            detail=f"unsupported content type: {file.content_type!r}; "
            "expected jpeg, png, or webp",
        )
    if not prompt.strip():
        raise HTTPException(status_code=422, detail="prompt must not be empty")

    job_id = uuid4()
    raw_key = f"{job_id}.{ext}"
    data = await file.read()
    await run_in_threadpool(
        storage.upload_bytes, settings.raw_bucket, raw_key, data, file.content_type
    )

    job = Job(id=job_id, raw_key=raw_key, prompt=prompt, status=JobStatus.PENDING)
    session.add(job)
    await session.commit()

    # M2: publish segment.request{job_id, raw_key, prompt} on NATS here.
    log.info("image.created", job_id=str(job_id), prompt=prompt, raw_key=raw_key)
    return JobCreated(job_id=job_id, status=JobStatus.PENDING)


@router.get("/images", response_model=list[JobRead])
async def list_images(
    limit: int = Query(20, ge=1, le=100),
    before: datetime | None = Query(
        None, description="Return jobs uploaded strictly before this timestamp"
    ),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> list[JobRead]:
    stmt = select(Job).order_by(Job.uploaded_at.desc(), Job.id.desc())
    if before is not None:
        stmt = stmt.where(Job.uploaded_at < before)
    stmt = stmt.limit(limit)
    jobs = (await session.execute(stmt)).scalars().all()
    return [await _to_read(j, storage, settings) for j in jobs]


@router.get("/images/{job_id}", response_model=JobRead)
async def get_image(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> JobRead:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return await _to_read(job, storage, settings)
