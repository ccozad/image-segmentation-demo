from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nats_url: str = "nats://nats:4222"

    # Hugging Face token for the gated facebook/sam3.1 checkpoint (M3).
    # Required to run the real model; the worker fails fast if it is missing.
    hf_token: str | None = None

    s3_endpoint: str | None = None
    s3_region: str = "us-east-1"
    aws_access_key_id: str = "minioadmin"
    aws_secret_access_key: str = "minioadmin"

    raw_bucket: str = "raw"
    annotated_bucket: str = "annotated"


@lru_cache
def get_settings() -> Settings:
    return Settings()
