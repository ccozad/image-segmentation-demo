from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables.

    Variable names are case-insensitive (DATABASE_URL -> database_url).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://segdemo:segdemo@postgres:5432/segdemo"

    nats_url: str = "nats://nats:4222"

    # Browser origins allowed to call the API (the React frontend, M4).
    # Override via CORS_ORIGINS as a JSON array in prod.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Object storage. When s3_endpoint is set (dev/MinIO) clients use path-style
    # addressing; when unset (prod) they fall back to default AWS S3 (M5).
    s3_endpoint: str | None = None
    # Endpoint baked into presigned URLs. In compose the API reaches MinIO at
    # http://minio:9000, but a browser/curl on the host needs http://localhost:9000,
    # so presigning uses this when set.
    s3_public_endpoint: str | None = None
    s3_region: str = "us-east-1"
    aws_access_key_id: str = "minioadmin"
    aws_secret_access_key: str = "minioadmin"

    raw_bucket: str = "raw"
    annotated_bucket: str = "annotated"

    presigned_url_ttl: int = 900

    @property
    def presign_endpoint(self) -> str | None:
        """Endpoint to sign GET URLs against (public if configured)."""
        return self.s3_public_endpoint or self.s3_endpoint


@lru_cache
def get_settings() -> Settings:
    return Settings()
