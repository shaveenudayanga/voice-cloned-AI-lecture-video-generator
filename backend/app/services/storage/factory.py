# SPDX-License-Identifier: Apache-2.0
from app.services.storage.interface import BlobStore
from app.services.storage.s3_adapter import S3BlobStore


def get_blob_store() -> BlobStore:
    return S3BlobStore()
