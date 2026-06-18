import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import Settings


class Storage:
    """boto3 wrapper for the worker: download raw, upload annotated, metadata head."""

    def __init__(self, settings: Settings) -> None:
        addressing = "path" if settings.s3_endpoint else "auto"
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.s3_region,
            config=Config(
                signature_version="s3v4", s3={"addressing_style": addressing}
            ),
        )

    def download_bytes(self, bucket: str, key: str) -> bytes:
        resp = self._client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    def upload_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        extra: dict = {}
        if metadata:
            extra["Metadata"] = {k: str(v) for k, v in metadata.items()}
        self._client.put_object(
            Bucket=bucket, Key=key, Body=data, ContentType=content_type, **extra
        )

    def head(self, bucket: str, key: str) -> dict[str, str] | None:
        """Return the object's user metadata, or None if it does not exist.

        Used for idempotency: a redelivered request whose annotated output
        already exists recovers mask_count/processing_ms from the metadata
        instead of re-running (expensive) GPU inference.
        """
        try:
            resp = self._client.head_object(Bucket=bucket, Key=key)
            return resp.get("Metadata", {})
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
