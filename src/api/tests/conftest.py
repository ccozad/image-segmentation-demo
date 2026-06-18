import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import get_session
from app.main import app
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

    def check(self) -> None:
        return None


@pytest.fixture
def fake_storage() -> FakeStorage:
    return FakeStorage()


@pytest_asyncio.fixture
async def client(fake_storage: FakeStorage):
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()
