from app.config import Settings
from app.storage import Storage


def test_dev_uses_minio_endpoint_and_path_style():
    storage = Storage(
        Settings(
            s3_endpoint="http://minio:9000",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
        )
    )
    assert storage._client.meta.endpoint_url == "http://minio:9000"
    assert storage._client.meta.config.s3["addressing_style"] == "path"


def test_prod_falls_back_to_aws_with_default_creds():
    # No endpoint, no static creds (instance role) -> real S3, virtual-hosted.
    storage = Storage(Settings(s3_endpoint=None))
    assert "amazonaws.com" in storage._client.meta.endpoint_url
    assert storage._client.meta.config.s3["addressing_style"] == "auto"


def test_public_endpoint_used_for_presigning():
    storage = Storage(
        Settings(
            s3_endpoint="http://minio:9000",
            s3_public_endpoint="http://localhost:9000",
        )
    )
    # Uploads go to the internal endpoint; presigned URLs to the public one.
    assert storage._client.meta.endpoint_url == "http://minio:9000"
    assert storage._presign_client.meta.endpoint_url == "http://localhost:9000"
