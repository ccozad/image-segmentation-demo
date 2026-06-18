import json
from uuid import UUID

import nats
from nats.js import JetStreamContext

# Shared with the API. One JetStream stream captures all segment.* subjects;
# the worker consumes segment.request and publishes segment.status/result.
STREAM = "SEGMENT"
SUBJECTS = ["segment.request", "segment.status", "segment.result"]
SUBJECT_REQUEST = "segment.request"
SUBJECT_STATUS = "segment.status"
SUBJECT_RESULT = "segment.result"

STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


async def connect(url: str):
    nc = await nats.connect(
        url,
        max_reconnect_attempts=-1,  # reconnect forever
        reconnect_time_wait=2,
    )
    return nc, nc.jetstream()


async def ensure_stream(js: JetStreamContext) -> None:
    """Create the shared stream if it does not exist (idempotent / race-safe)."""
    try:
        await js.stream_info(STREAM)
    except Exception:
        try:
            await js.add_stream(name=STREAM, subjects=SUBJECTS)
        except Exception:
            # Lost a creation race with the API — that's fine.
            await js.stream_info(STREAM)


class Publisher:
    def __init__(self, js: JetStreamContext) -> None:
        self._js = js

    async def publish_status(self, job_id: str | UUID, status: str) -> None:
        payload = {"job_id": str(job_id), "status": status}
        await self._js.publish(SUBJECT_STATUS, json.dumps(payload).encode())

    async def publish_result(
        self,
        job_id: str | UUID,
        annotated_key: str | None = None,
        mask_count: int | None = None,
        processing_ms: int | None = None,
        status: str = STATUS_DONE,
        error: str | None = None,
    ) -> None:
        payload = {
            "job_id": str(job_id),
            "status": status,
            "annotated_key": annotated_key,
            "mask_count": mask_count,
            "processing_ms": processing_ms,
            "error": error,
        }
        await self._js.publish(SUBJECT_RESULT, json.dumps(payload).encode())
