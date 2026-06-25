# SPDX-License-Identifier: Apache-2.0
from typing import cast

import structlog
from aioboto3 import Session

from app.core.config import settings

logger = structlog.get_logger(__name__)


class S3BlobStore:
    """S3-compatible blob store. Tested against SeaweedFS; works unchanged with AWS S3 / R2."""

    def __init__(self) -> None:
        self._session = Session()
        self._kwargs = {
            "endpoint_url": settings.storage_endpoint_url,
            "aws_access_key_id": settings.storage_access_key,
            "aws_secret_access_key": settings.storage_secret_key,
            "region_name": settings.storage_region,
        }

    async def put(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        async with self._session.client("s3", **self._kwargs) as s3:
            await s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        logger.debug("blob_put", bucket=bucket, key=key, size=len(data))
        return key

    async def get(self, bucket: str, key: str) -> bytes:
        async with self._session.client("s3", **self._kwargs) as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            return cast(bytes, await response["Body"].read())

    async def delete(self, bucket: str, key: str) -> None:
        async with self._session.client("s3", **self._kwargs) as s3:
            await s3.delete_object(Bucket=bucket, Key=key)

    async def presign_get(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        async with self._session.client("s3", **self._kwargs) as s3:
            return cast(
                str,
                await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": key},
                    ExpiresIn=expires_in,
                ),
            )

    async def ensure_bucket(self, bucket: str) -> None:
        async with self._session.client("s3", **self._kwargs) as s3:
            try:
                await s3.head_bucket(Bucket=bucket)
            except Exception:
                await s3.create_bucket(Bucket=bucket)
                logger.info("bucket_created", bucket=bucket)
