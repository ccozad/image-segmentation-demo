from tests.conftest import FakeSegmenter, FakePublisher, FakeStorage
from worker.worker import handle_request

RAW = "raw"
ANNOTATED = "annotated"
JOB_ID = "11111111-1111-1111-1111-111111111111"


def _data():
    return {"job_id": JOB_ID, "raw_key": f"{JOB_ID}.png", "prompt": "cars"}


async def test_handle_request_full_loop(settings, png_bytes):
    storage = FakeStorage(seed={(RAW, f"{JOB_ID}.png"): png_bytes})
    segmenter = FakeSegmenter(png=b"annotated-png", mask_count=3)
    pub = FakePublisher()

    await handle_request(_data(), storage, segmenter, pub, settings)

    assert pub.statuses == [(JOB_ID, "processing")]
    assert len(pub.results) == 1
    result = pub.results[0]
    assert result["status"] == "done"
    assert result["annotated_key"] == f"{JOB_ID}.png"
    assert result["mask_count"] == 3
    assert result["processing_ms"] >= 0
    # Annotated uploaded with mask-count metadata for idempotent recovery.
    assert (ANNOTATED, f"{JOB_ID}.png") in storage.objects
    assert storage.objects[(ANNOTATED, f"{JOB_ID}.png")][1]["mask-count"] == "3"


async def test_handle_request_idempotent_skip(settings, png_bytes):
    # Annotated already present (with metadata) -> no re-inference, no re-upload.
    storage = FakeStorage(seed={(RAW, f"{JOB_ID}.png"): png_bytes})
    storage.objects[(ANNOTATED, f"{JOB_ID}.png")] = (b"old", {"mask-count": "5", "processing-ms": "900"})
    segmenter = FakeSegmenter(png=b"new", mask_count=1)
    pub = FakePublisher()

    await handle_request(_data(), storage, segmenter, pub, settings)

    assert segmenter.calls == 0  # inference skipped
    assert storage.uploads == []  # no re-upload
    assert pub.results[0]["mask_count"] == 5  # recovered from metadata
    assert pub.results[0]["processing_ms"] == 900


async def test_handle_request_inference_failure(settings, png_bytes):
    storage = FakeStorage(seed={(RAW, f"{JOB_ID}.png"): png_bytes})
    segmenter = FakeSegmenter(png=b"x", error="boom")
    pub = FakePublisher()

    await handle_request(_data(), storage, segmenter, pub, settings)

    assert storage.uploads == []
    assert len(pub.results) == 1
    assert pub.results[0]["status"] == "failed"
    assert pub.results[0]["error"] == "boom"


async def test_handle_request_zero_masks(settings, png_bytes):
    storage = FakeStorage(seed={(RAW, f"{JOB_ID}.png"): png_bytes})
    segmenter = FakeSegmenter(png=png_bytes, mask_count=0)
    pub = FakePublisher()

    await handle_request(_data(), storage, segmenter, pub, settings)

    assert pub.results[0]["status"] == "done"
    assert pub.results[0]["mask_count"] == 0
