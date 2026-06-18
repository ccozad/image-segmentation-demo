from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class JobCreated(BaseModel):
    job_id: UUID
    status: str


class JobRead(BaseModel):
    id: UUID
    prompt: str
    status: str
    mask_count: int | None
    processing_ms: int | None
    uploaded_at: datetime
    completed_at: datetime | None
    error: str | None
    raw_url: str | None
    annotated_url: str | None
