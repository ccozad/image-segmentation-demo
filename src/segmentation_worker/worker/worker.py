import asyncio
import json
import random
import signal
import time
from collections.abc import Callable

import structlog

from .config import Settings, get_settings
from .messaging import (
    SUBJECT_REQUEST,
    STATUS_PROCESSING,
    Publisher,
    connect,
    ensure_stream,
)
from .processing import render_annotation
from .storage import Storage

log = structlog.get_logger()


def process_job(
    data: dict,
    storage: Storage,
    raw_bucket: str,
    annotated_bucket: str,
    sleep: Callable[[], None] | None = None,
) -> dict:
    """Blocking work: download, fake-annotate, upload. Idempotent re-run safe.

    Returns the segment.result payload fields. Runs off the event loop via
    ``asyncio.to_thread`` so blocking boto3/Pillow calls don't stall NATS.
    """
    job_id = data["job_id"]
    raw_key = data["raw_key"]
    prompt = data["prompt"]
    annotated_key = f"{job_id}.png"

    start = time.monotonic()
    # Idempotency: a redelivered request whose output already exists is a no-op
    # for the expensive work; we still report the result so the API converges.
    if storage.object_exists(annotated_bucket, annotated_key):
        log.info("job.skip_existing", job_id=job_id, annotated_key=annotated_key)
    else:
        raw = storage.download_bytes(raw_bucket, raw_key)
        annotated = render_annotation(raw, prompt)
        if sleep is None:
            time.sleep(random.uniform(1.0, 2.0))  # simulate work
        else:
            sleep()
        storage.upload_bytes(annotated_bucket, annotated_key, annotated, "image/png")

    processing_ms = int((time.monotonic() - start) * 1000)
    return {
        "annotated_key": annotated_key,
        "mask_count": 1,
        "processing_ms": processing_ms,
    }


async def handle_request(
    data: dict,
    storage: Storage,
    publisher: Publisher,
    settings: Settings,
    sleep: Callable[[], None] | None = None,
) -> None:
    job_id = data["job_id"]
    log.info("job.received", job_id=job_id, prompt=data.get("prompt"))
    await publisher.publish_status(job_id, STATUS_PROCESSING)
    result = await asyncio.to_thread(
        process_job,
        data,
        storage,
        settings.raw_bucket,
        settings.annotated_bucket,
        sleep,
    )
    await publisher.publish_result(job_id, **result)
    log.info("job.done", job_id=job_id, **result)


async def main() -> None:
    settings = get_settings()
    storage = Storage(settings)
    nc, js = await connect(settings.nats_url)
    await ensure_stream(js)
    publisher = Publisher(js)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    async def on_request(msg) -> None:
        try:
            data = json.loads(msg.data)
            await handle_request(data, storage, publisher, settings)
            await msg.ack()
        except Exception:
            log.exception("job.failed")
            # Negative-ack so JetStream redelivers (at-least-once).
            await msg.nak()

    # Durable consumer => unacked messages are redelivered after a restart.
    await js.subscribe(
        SUBJECT_REQUEST, durable="seg-worker", manual_ack=True, cb=on_request
    )
    log.info("worker.ready", nats=settings.nats_url)

    await stop.wait()
    log.info("worker.shutdown")
    await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
