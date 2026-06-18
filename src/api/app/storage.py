from functools import lru_cache

import boto3
from botocore.client import Config

from .config import Settings, get_settings


class Storage:
    """Thin boto3 wrapper for S3 / MinIO.

    All methods are synchronous (boto3 is blocking); call them from request
    handlers via ``starlette.concurrency.run_in_threadpool``.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        addressing = "path" if settings.s3_endpoint else "auto"
        common = dict(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.s3_region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": addressing},
            ),
        )
        self._client = boto3.client("s3", endpoint_url=settings.s3_endpoint, **common)
        # Presigned URLs must be signed against the host the *caller* will hit.
        if settings.presign_endpoint and settings.presign_endpoint != settings.s3_endpoint:
            self._presign_client = boto3.client(
                "s3", endpoint_url=settings.presign_endpoint, **common
            )
        else:
            self._presign_client = self._client

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=bucket, Key=key, Body=data, ContentType=content_type
        )

    def presigned_get(self, bucket: str, key: str, ttl: int) -> str:
        return self._presign_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl,
        )

    def check(self) -> None:
        """Connectivity probe for healthchecks (raises on failure)."""
        self._client.list_buckets()


@lru_cache
def get_storage() -> Storage:
    return Storage(get_settings())
