import os
import asyncio
import tempfile
from pathlib import Path
from botocore.exceptions import ClientError

BUCKET = os.environ.get("CLIPS_BUCKET", "clipbot-clips")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT_URL", "http://minio:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "minioadmin")


def _make_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1",
    )


def raw_key(trace_id: str) -> str:
    return f"{trace_id}/raw.mp4"


def formatted_key(trace_id: str) -> str:
    return f"{trace_id}/formatted.mp4"


def tmp_path(name: str) -> Path:
    return Path(tempfile.gettempdir()) / name


async def upload(local_path: Path, key: str) -> None:
    def _do():
        _make_client().upload_file(str(local_path), BUCKET, key)
    await asyncio.to_thread(_do)


async def download(key: str, local_path: Path) -> None:
    def _do():
        _make_client().download_file(BUCKET, key, str(local_path))
    await asyncio.to_thread(_do)


async def delete_job(trace_id: str) -> None:
    def _do():
        client = _make_client()
        for k in (raw_key(trace_id), formatted_key(trace_id)):
            try:
                client.delete_object(Bucket=BUCKET, Key=k)
            except ClientError:
                pass
    await asyncio.to_thread(_do)


async def ensure_bucket() -> None:
    def _do():
        client = _make_client()
        try:
            client.create_bucket(Bucket=BUCKET)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise
    await asyncio.to_thread(_do)
