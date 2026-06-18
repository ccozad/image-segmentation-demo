import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from .config import get_settings
from .events import on_result, on_status
from .messaging import (
    Publisher,
    connect,
    ensure_stream,
    start_event_subscribers,
)
from .routes import health, images


def _configure_logging() -> None:
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


_configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to JetStream, expose a publisher, and run the event subscriber."""
    settings = get_settings()
    nc, js = await connect(settings.nats_url)
    await ensure_stream(js)
    app.state.nats = nc
    app.state.publisher = Publisher(js)
    await start_event_subscribers(js, on_status, on_result)
    log.info("api.ready", nats=settings.nats_url)
    try:
        yield
    finally:
        # Drain (not unsubscribe): keep the durable consumers' ack progress so a
        # restart resumes from the last processed event.
        await nc.drain()


app = FastAPI(title="Image Segmentation Demo API", version="0.1.0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(images.router)
