# SPDX-License-Identifier: Apache-2.0
from typing import Protocol, runtime_checkable


@runtime_checkable
class BlobStore(Protocol):
    """Pluggable object storage interface. Works with SeaweedFS, AWS S3, R2, Backblaze B2."""

    async def put(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload bytes and return the canonical key."""
        ...

    async def get(self, bucket: str, key: str) -> bytes:
        """Download and return blob bytes."""
        ...

    async def delete(self, bucket: str, key: str) -> None:
        """Delete a blob. Idempotent — does not raise if the key does not exist."""
        ...

    async def presign_get(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        """Return a pre-signed URL valid for `expires_in` seconds."""
        ...

    async def ensure_bucket(self, bucket: str) -> None:
        """Create the bucket if it does not exist."""
        ...
