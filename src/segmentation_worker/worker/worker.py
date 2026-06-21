import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

import structlog
from nats.errors import TimeoutError as NatsTimeoutError

from .config import Settings, get_settings
from .messaging import (
    SUBJECT_REQUEST,
    STATUS_FAILED,
    STATUS_PROCESSING,
    Publisher,
    connect,
    ensure_stream,
)
from .segmentation import SegmentationError, Segmenter
from .storage import Storage

log = structlog.get_logger()


def process_job(
    data: dict,
    storage: Storage,
    segmenter,
    raw_bucket: str,
    annotated_bucket: str,
) -> dict:
    """Blocking work: download, segment, upload. Runs off the event loop via
    ``asyncio.to_thread``.

    Idempotent: a redelivered request whose annotated output already exists
    recovers its metadata instead of re-running GPU inference. Raises
    SegmentationError if inference fails (caller reports the job as failed).
    """
    job_id = data["job_id"]
    raw_key = data["raw_key"]
    prompt = data["prompt"]
    annotated_key = f"{job_id}.png"

    existing = storage.head(annotated_bucket, annotated_key)
    if existing is not None:
        log.info("job.skip_existing", job_id=job_id, annotated_key=annotated_key)
        return {
            "annotated_key": annotated_key,
            "mask_count": int(existing.get("mask-count", 0) or 0),
            "processing_ms": int(existing.get("processing-ms", 0) or 0),
        }

    raw = storage.download_bytes(raw_bucket, raw_key)
    start = time.monotonic()
    annotated_png, mask_count = segmenter.segment(raw, prompt)
    processing_ms = int((time.monotonic() - start) * 1000)

    storage.upload_bytes(
        annotated_bucket,
        annotated_key,
        annotated_png,
        "image/png",
        metadata={"mask-count": mask_count, "processing-ms": processing_ms},
    )
    return {
        "annotated_key": annotated_key,
        "mask_count": mask_count,
        "processing_ms": processing_ms,
    }


async def handle_request(
    data: dict,
    storage: Storage,
    segmenter,
    publisher: Publisher,
    settings: Settings,
) -> None:
    job_id = data["job_id"]
    log.info("job.received", job_id=job_id, prompt=data.get("prompt"))
    await publisher.publish_status(job_id, STATUS_PROCESSING)
    try:
        result = await asyncio.to_thread(
            process_job,
            data,
            storage,
            segmenter,
            settings.raw_bucket,
            settings.annotated_bucket,
        )
    except SegmentationError as exc:
        # Deterministic inference failure -> report failed and ack (no redelivery).
        log.warning("job.failed", job_id=job_id, error=str(exc))
        await publisher.publish_result(
            job_id, status=STATUS_FAILED, error=str(exc)
        )
        return
    await publisher.publish_result(job_id, **result)
    log.info("job.done", job_id=job_id, **result)


# Shared durable consumer name. A JetStream **pull** consumer lets any number of
# worker processes bind the same durable and have requests load-balanced across
# them (a push consumer would let only one bind) — so this scales to a pool of
# spot GPU nodes that each just subscribe. One worker is the degenerate case.
WORKER_DURABLE = "seg-workers"


async def consume(
    js,
    storage: Storage,
    segmenter,
    publisher: Publisher,
    settings: Settings,
    stop: asyncio.Event,
    *,
    durable: str = WORKER_DURABLE,
    on_ready=None,
) -> None:
    """Pull `segment.request` messages and process them until `stop` is set.

    Run one of these per worker process; multiple instances binding the same
    durable share the queue (each message goes to exactly one worker, with
    at-least-once redelivery on crash).
    """
    psub = await js.pull_subscribe(SUBJECT_REQUEST, durable=durable)
    if on_ready is not None:
        on_ready()
    log.info("worker.ready", durable=durable)

    while not stop.is_set():
        try:
            msgs = await psub.fetch(batch=1, timeout=1)
        except NatsTimeoutError:
            continue  # no work right now; poll again
        except Exception:
            log.exception("worker.fetch_error")
            await asyncio.sleep(0.5)
            continue
        for msg in msgs:
            try:
                data = json.loads(msg.data)
                await handle_request(data, storage, segmenter, publisher, settings)
                await msg.ack()
            except Exception:
                # Non-inference failure (download / NATS / etc.) -> redeliver.
                log.exception("job.error")
                await msg.nak()


async def main() -> None:
    settings = get_settings()
    if not settings.hf_token:
        log.error("worker.no_hf_token", detail="HF_TOKEN is required for the gated SAM 3 checkpoint")
        sys.exit(1)

    storage = Storage(settings)
    # Preload the model once (large; per-request reload would be unusable).
    segmenter = Segmenter()

    nc, js = await connect(settings.nats_url)
    await ensure_stream(js)
    publisher = Publisher(js)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    # Liveness marker for the container HEALTHCHECK: written once the model is
    # loaded and we're subscribed (i.e. ready to process).
    health_file = Path(os.environ.get("WORKER_HEALTH_FILE", "/tmp/worker-ready"))
    await consume(
        js, storage, segmenter, publisher, settings, stop,
        on_ready=health_file.touch,
    )

    log.info("worker.shutdown")
    health_file.unlink(missing_ok=True)
    await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
