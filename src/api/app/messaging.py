import json
from collections.abc import Awaitable, Callable
from uuid import UUID

import nats
import structlog
from fastapi import Request
from nats.js import JetStreamContext

log = structlog.get_logger()

# Shared with the worker. One JetStream stream captures all segment.* subjects.
STREAM = "SEGMENT"
SUBJECTS = ["segment.request", "segment.status", "segment.result"]
SUBJECT_REQUEST = "segment.request"
SUBJECT_STATUS = "segment.status"
SUBJECT_RESULT = "segment.result"


async def connect(url: str):
    nc = await nats.connect(url, max_reconnect_attempts=-1, reconnect_time_wait=2)
    return nc, nc.jetstream()


async def ensure_stream(js: JetStreamContext) -> None:
    """Create the shared stream if missing (idempotent / race-safe vs the worker)."""
    try:
        await js.stream_info(STREAM)
    except Exception:
        try:
            await js.add_stream(name=STREAM, subjects=SUBJECTS)
        except Exception:
            await js.stream_info(STREAM)


class Publisher:
    """Publishes segment.request when a new image is uploaded."""

    def __init__(self, js: JetStreamContext) -> None:
        self._js = js

    async def publish_request(self, job_id: str | UUID, raw_key: str, prompt: str) -> None:
        payload = {"job_id": str(job_id), "raw_key": raw_key, "prompt": prompt}
        await self._js.publish(SUBJECT_REQUEST, json.dumps(payload).encode())


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher


async def start_event_subscribers(
    js: JetStreamContext,
    on_status: Callable[[dict], Awaitable[None]],
    on_result: Callable[[dict], Awaitable[None]],
) -> list:
    """Bind durable consumers that translate worker events into DB updates.

    Durable => events published while the API was down are delivered on restart.
    """

    def _make_cb(handler, label):
        async def _cb(msg) -> None:
            try:
                await handler(json.loads(msg.data))
                await msg.ack()
            except Exception:
                log.exception("event.failed", subject=label)
                await msg.nak()

        return _cb

    sub_status = await js.subscribe(
        SUBJECT_STATUS,
        durable="seg-api-status",
        manual_ack=True,
        cb=_make_cb(on_status, SUBJECT_STATUS),
    )
    sub_result = await js.subscribe(
        SUBJECT_RESULT,
        durable="seg-api-result",
        manual_ack=True,
        cb=_make_cb(on_result, SUBJECT_RESULT),
    )
    return [sub_status, sub_result]
