# A minimal 1x1 PNG so uploads carry real-ish bytes.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f9b0000000049454e44ae426082"
)


async def test_upload_then_list_and_detail(client, fake_storage):
    resp = await client.post(
        "/images",
        files={"file": ("sample.png", PNG_BYTES, "image/png")},
        data={"prompt": "cars"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    job_id = body["job_id"]

    # Raw bytes persisted to the raw bucket under {id}.png.
    assert ("raw", f"{job_id}.png") in fake_storage.objects

    # History list shows the new job, newest-first, pending, with a raw URL.
    resp = await client.get("/images")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == job_id
    assert items[0]["status"] == "pending"
    assert items[0]["mask_count"] is None
    assert items[0]["raw_url"]
    assert items[0]["annotated_url"] is None

    # Detail returns the same shape.
    resp = await client.get(f"/images/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["prompt"] == "cars"


async def test_rejects_unsupported_content_type(client):
    resp = await client.post(
        "/images",
        files={"file": ("note.txt", b"hello", "text/plain")},
        data={"prompt": "cars"},
    )
    assert resp.status_code == 415


async def test_detail_404_for_unknown_id(client):
    resp = await client.get("/images/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_healthz_ok(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
