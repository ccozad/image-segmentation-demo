"""Integration test for the JetStream pull-consumer fan-out.

Runs a *real* NATS JetStream (throwaway Docker container) and several worker
`consume()` loops bound to the same durable, with the GPU `Segmenter` faked out.
Proves the scaling claim without a GPU: each request is processed exactly once
and the work spreads across the pool.

Skipped automatically if Docker or the nats client aren't available.
"""
import asyncio
import json
import shutil
import socket
import subprocess

import pytest
import pytest_asyncio

from tests.conftest import FakePublisher, FakeSegmenter, FakeStorage
from worker.config import Settings
from worker.messaging import SUBJECT_REQUEST, ensure_stream
from worker.worker import consume

nats = pytest.importorskip("nats")

pytestmark = pytest.mark.integration

RAW = "raw"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest_asyncio.fixture
async def nats_url():
    if shutil.which("docker") is None:
        pytest.skip("docker not available")
    port = _free_port()
    name = f"segdemo-nats-test-{port}"
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name,
         "-p", f"{port}:4222", "nats:2-alpine", "--jetstream"],
        check=True, capture_output=True,
    )
    url = f"nats://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                nc = await nats.connect(url, connect_timeout=1)
                await nc.close()
                break
            except Exception:
                await asyncio.sleep(0.2)
        else:
            pytest.skip("nats did not become ready")
        yield url
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


async def test_pull_consumer_fans_out_each_message_once(nats_url):
    settings = Settings()
    job_ids = [f"job-{i}" for i in range(6)]

    # Enqueue the requests on a JetStream stream.
    pub_nc = await nats.connect(nats_url)
    pub_js = pub_nc.jetstream()
    await ensure_stream(pub_js)
    for jid in job_ids:
        payload = {"job_id": jid, "raw_key": f"{jid}.png", "prompt": "cars"}
        await pub_js.publish(SUBJECT_REQUEST, json.dumps(payload).encode())

    # Three independent workers (separate connections), all binding the same
    # durable pull consumer.
    n_workers = 3
    stop = asyncio.Event()
    conns, pubs, tasks = [], [], []
    for _ in range(n_workers):
        nc = await nats.connect(nats_url)
        js = nc.jetstream()
        await ensure_stream(js)
        storage = FakeStorage(seed={(RAW, f"{j}.png"): b"raw" for j in job_ids})
        segmenter = FakeSegmenter(png=b"annotated", mask_count=2, delay=0.1)
        fp = FakePublisher()
        conns.append(nc)
        pubs.append(fp)
        tasks.append(asyncio.create_task(consume(js, storage, segmenter, fp, settings, stop)))

    try:
        # Wait until the whole batch has been processed across the pool.
        for _ in range(100):  # up to ~10s
            if sum(len(p.results) for p in pubs) >= len(job_ids):
                break
            await asyncio.sleep(0.1)
    finally:
        stop.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        for nc in conns:
            await nc.drain()
        await pub_nc.drain()

    processed = sorted(r["job_id"] for p in pubs for r in p.results)
    # Each request processed exactly once — no loss, no duplication.
    assert processed == sorted(job_ids)
    # Work genuinely fanned out across the pool (not all on one worker).
    assert sum(1 for p in pubs if p.results) >= 2
