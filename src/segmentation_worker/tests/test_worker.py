from tests.conftest import FakePublisher, FakeStorage
from worker.worker import handle_request

RAW = "raw"
ANNOTATED = "annotated"
JOB_ID = "11111111-1111-1111-1111-111111111111"


async def test_handle_request_full_loop(settings, png_bytes):
    storage = FakeStorage(seed={(RAW, f"{JOB_ID}.png"): png_bytes})
    pub = FakePublisher()
    data = {"job_id": JOB_ID, "raw_key": f"{JOB_ID}.png", "prompt": "cars"}

    await handle_request(data, storage, pub, settings, sleep=lambda: None)

    # Status published first, then result.
    assert pub.statuses == [(JOB_ID, "processing")]
    assert len(pub.results) == 1
    result = pub.results[0]
    assert result["status"] == "done"
    assert result["annotated_key"] == f"{JOB_ID}.png"
    assert result["mask_count"] == 1
    assert result["processing_ms"] >= 0
    # Annotated object was uploaded.
    assert (ANNOTATED, f"{JOB_ID}.png") in storage.objects
    assert storage.uploads == [(ANNOTATED, f"{JOB_ID}.png")]


async def test_handle_request_idempotent_skip(settings, png_bytes):
    # Annotated already present -> redelivery must not re-upload, but still reports.
    storage = FakeStorage(
        seed={
            (RAW, f"{JOB_ID}.png"): png_bytes,
            (ANNOTATED, f"{JOB_ID}.png"): b"already-done",
        }
    )
    pub = FakePublisher()
    data = {"job_id": JOB_ID, "raw_key": f"{JOB_ID}.png", "prompt": "cars"}

    await handle_request(data, storage, pub, settings, sleep=lambda: None)

    assert storage.uploads == []  # no re-upload
    assert storage.objects[(ANNOTATED, f"{JOB_ID}.png")] == b"already-done"  # untouched
    assert len(pub.results) == 1  # still publishes a result
    assert pub.results[0]["annotated_key"] == f"{JOB_ID}.png"
