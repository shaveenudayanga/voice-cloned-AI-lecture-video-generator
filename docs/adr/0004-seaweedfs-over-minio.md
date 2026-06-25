# ADR-0004 — Replace MinIO with SeaweedFS as Object Storage

**Status:** Accepted  
**Date:** 2026-06-25

## Context

MinIO Community Edition was effectively archived in February 2026 when MinIO Inc. shifted entirely to their enterprise product. The Community Edition is no longer receiving security patches. We need an S3-compatible self-hosted object store for slide images, audio clips, and video artifacts.

## Decision

Use **SeaweedFS `^3.80`** (Apache-2.0, single-binary mode). SeaweedFS was adopted by Kubeflow Pipelines as its default storage backend after the MinIO archive, making it the community consensus successor.

The application layer is unaffected because all storage access goes through the `BlobStore` protocol in `services/storage/interface.py` using the `aioboto3` S3-compatible client. Swapping back to MinIO, AWS S3, Cloudflare R2, or Backblaze B2 is an env-var change (`STORAGE_ENDPOINT_URL`), not a code change — this is the proof that the adapter pattern works.

## Consequences

- SeaweedFS single-binary mode is appropriate for our scale (one professor, a few videos per week).
- Apache-2.0 license is clean with no restrictions.
- For production, `chrislusf/seaweedfs:latest` should be pinned by digest in the prod compose overlay.
