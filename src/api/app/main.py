import logging

import structlog
from fastapi import FastAPI

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

app = FastAPI(title="Image Segmentation Demo API", version="0.1.0")
app.include_router(health.router)
app.include_router(images.router)
