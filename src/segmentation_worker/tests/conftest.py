import io

import pytest
from PIL import Image

from worker.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


class FakeStorage:
    """In-memory stand-in for the boto3 Storage."""

    def __init__(self, seed: dict[tuple[str, str], bytes] | None = None) -> None:
        self.objects: dict[tuple[str, str], bytes] = dict(seed or {})
        self.uploads: list[tuple[str, str]] = []

    def download_bytes(self, bucket: str, key: str) -> bytes:
        return self.objects[(bucket, key)]

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self.objects[(bucket, key)] = data
        self.uploads.append((bucket, key))

    def object_exists(self, bucket: str, key: str) -> bool:
        return (bucket, key) in self.objects


class FakePublisher:
    def __init__(self) -> None:
        self.statuses: list[tuple[str, str]] = []
        self.results: list[dict] = []

    async def publish_status(self, job_id, status) -> None:
        self.statuses.append((str(job_id), status))

    async def publish_result(self, job_id, annotated_key, mask_count, processing_ms, status="done") -> None:
        self.results.append(
            {
                "job_id": str(job_id),
                "status": status,
                "annotated_key": annotated_key,
                "mask_count": mask_count,
                "processing_ms": processing_ms,
            }
        )
