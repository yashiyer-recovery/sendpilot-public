"""S3-compatible object storage (MinIO locally).

boto3 is sync; calls run in a thread so they don't block the event loop. The
bucket is created on demand and calls retry briefly so MinIO startup timing
never breaks an upload. In production the bucket enforces SSE-KMS via bucket
policy (PRD §16); locally the MinIO default is used.
"""

from __future__ import annotations

import asyncio
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from ..config import settings


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name=settings.object_storage_region,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def _ensure_bucket_sync(client) -> None:
    try:
        client.head_bucket(Bucket=settings.object_storage_bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=settings.object_storage_bucket)
        except ClientError as exc:  # already exists / racing creator
            if "BucketAlreadyOwnedByYou" not in str(exc) and "BucketAlreadyExists" not in str(exc):
                raise


async def ensure_bucket() -> None:
    def _do() -> None:
        # Retry briefly in case MinIO is still coming up at boot.
        last: Exception | None = None
        for _ in range(10):
            try:
                _ensure_bucket_sync(_client())
                return
            except (EndpointConnectionError, ClientError) as exc:
                last = exc
                time.sleep(1)
        if last:
            raise last

    await asyncio.to_thread(_do)


async def put_object(key: str, data: bytes, content_type: str) -> None:
    def _do() -> None:
        client = _client()
        try:
            client.put_object(
                Bucket=settings.object_storage_bucket, Key=key, Body=data,
                ContentType=content_type,
            )
        except ClientError as exc:
            if "NoSuchBucket" not in str(exc):
                raise
            _ensure_bucket_sync(client)
            client.put_object(
                Bucket=settings.object_storage_bucket, Key=key, Body=data,
                ContentType=content_type,
            )

    await asyncio.to_thread(_do)


async def get_object(key: str) -> bytes:
    def _do() -> bytes:
        resp = _client().get_object(Bucket=settings.object_storage_bucket, Key=key)
        return resp["Body"].read()

    return await asyncio.to_thread(_do)


async def delete_object(key: str) -> None:
    def _do() -> None:
        _client().delete_object(Bucket=settings.object_storage_bucket, Key=key)

    await asyncio.to_thread(_do)
