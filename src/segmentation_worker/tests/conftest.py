import io

import pytest
from PIL import Image

from worker.config import Settings
from worker.segmentation import SegmentationError


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


class FakeStorage:
    """In-memory stand-in for the boto3 Storage (stores bytes + metadata)."""

    def __init__(self, seed: dict[tuple[str, str], bytes] | None = None) -> None:
        # key -> (data, metadata)
        self.objects: dict[tuple[str, str], tuple[bytes, dict]] = {
            k: (v, {}) for k, v in (seed or {}).items()
        }
        self.uploads: list[tuple[str, str]] = []

    def download_bytes(self, bucket: str, key: str) -> bytes:
        return self.objects[(bucket, key)][0]

    def upload_bytes(self, bucket, key, data, content_type, metadata=None) -> None:
        # S3 metadata values are always strings; mirror that here.
        meta = {k: str(v) for k, v in (metadata or {}).items()}
        self.objects[(bucket, key)] = (data, meta)
        self.uploads.append((bucket, key))

    def head(self, bucket: str, key: str) -> dict | None:
        entry = self.objects.get((bucket, key))
        return None if entry is None else entry[1]


class FakePublisher:
    def __init__(self) -> None:
        self.statuses: list[tuple[str, str]] = []
        self.results: list[dict] = []

    async def publish_status(self, job_id, status) -> None:
        self.statuses.append((str(job_id), status))

    async def publish_result(
        self,
        job_id,
        annotated_key=None,
        mask_count=None,
        processing_ms=None,
        status="done",
        error=None,
    ) -> None:
        self.results.append(
            {
                "job_id": str(job_id),
                "status": status,
                "annotated_key": annotated_key,
                "mask_count": mask_count,
                "processing_ms": processing_ms,
                "error": error,
            }
        )


class FakeSegmenter:
    """Stand-in for the SAM 3 Segmenter, so worker tests need no GPU."""

    def __init__(
        self,
        png: bytes,
        mask_count: int = 2,
        error: str | None = None,
        delay: float = 0.0,
    ) -> None:
        self._png = png
        self._mask_count = mask_count
        self._error = error
        self._delay = delay  # simulate work so a pool of workers interleaves
        self.calls = 0

    def segment(self, image_bytes: bytes, prompt: str) -> tuple[bytes, int]:
        self.calls += 1
        if self._delay:
            import time

            time.sleep(self._delay)
        if self._error is not None:
            raise SegmentationError(self._error)
        return self._png, self._mask_count
