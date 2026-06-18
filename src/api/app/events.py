from datetime import datetime, timezone
from uuid import UUID

import structlog

from .db import SessionLocal
from .models import Job, JobStatus

log = structlog.get_logger()


async def on_status(data: dict) -> None:
    """segment.status -> advance pending jobs to processing (guarded, idempotent)."""
    job_id = UUID(data["job_id"])
    status = data.get("status")
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        # Only move forward from pending; never regress a terminal state.
        if status == JobStatus.PROCESSING and job.status == JobStatus.PENDING:
            job.status = JobStatus.PROCESSING
            await session.commit()
            log.info("job.processing", job_id=str(job_id))


async def on_result(data: dict) -> None:
    """segment.result -> terminal state (done|failed) with metadata."""
    job_id = UUID(data["job_id"])
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if job is None:
            return
        if data.get("status") == JobStatus.FAILED:
            job.status = JobStatus.FAILED
        else:
            job.status = JobStatus.DONE
            job.annotated_key = data.get("annotated_key")
            job.mask_count = data.get("mask_count")
            job.processing_ms = data.get("processing_ms")
        job.completed_at = datetime.now(timezone.utc)
        await session.commit()
        log.info("job.completed", job_id=str(job_id), status=job.status)
