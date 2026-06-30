# SPDX-License-Identifier: Apache-2.0
# CPU worker + API image. GPU workers use Dockerfile.gpu.
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# LibreOffice is embedded here (not a separate service) for headless PPTX → PDF conversion.
# Using apt-get --no-install-recommends keeps the image lean (~300 MB additional).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    ffmpeg \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no [gpu] extras on CPU image)
RUN uv sync --frozen --no-dev

# Copy application source and Alembic config
COPY app/ ./app/
COPY alembic.ini ./

FROM base AS api
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker-cpu
CMD ["uv", "run", "celery", "-A", "app.tasks.celery_app", "worker", \
     "--loglevel=info", "--queues=cpu", "--concurrency=2"]
