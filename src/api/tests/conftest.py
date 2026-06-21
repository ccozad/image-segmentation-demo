import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import get_session
from app.main import app
from app.messaging import get_publisher
from app.models import Base
from app.storage import get_storage


class FakeStorage:
    """In-memory stand-in for the boto3 Storage, so tests need no MinIO."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self.objects[(bucket, key)] = (data, content_type)

    def presigned_get(self, bucket: str, key: str, ttl: int) -> str:
        return f"https://fake.local/{bucket}/{key}?ttl={ttl}"

    def delete(self, bucket: str, key: str) -> None:
        self.objects.pop((bucket, key), None)

    def check(self) -> None:
        return None


class FakePublisher:
    """Captures published segment.request messages (the lifespan/NATS is not
    started under ASGITransport, so the real publisher is never wired up)."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, str]] = []

    async def publish_request(self, job_id, raw_key, prompt) -> None:
        self.requests.append((str(job_id), raw_key, prompt))


@pytest.fixture
def fake_storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def fake_publisher() -> FakePublisher:
    return FakePublisher()


@pytest_asyncio.fixture
async def client(fake_storage: FakeStorage, fake_publisher: "FakePublisher"):
    # Single shared in-memory SQLite connection for the test's lifetime.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_storage] = lambda: fake_storage
    app.dependency_overrides[get_publisher] = lambda: fake_publisher

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()
