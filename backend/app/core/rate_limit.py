# SPDX-License-Identifier: Apache-2.0
"""slowapi rate limiting configuration.

Rate limit key: X-API-Key header value (not client IP — multiple faculty may share an
IP on a campus network). Falls back to IP if the header is absent.

Limit tiers:
  - upload endpoints (POST /slides/upload, POST /voices/): RATE_LIMIT_UPLOAD
  - generate/synthesize endpoints: RATE_LIMIT_GENERATE
  - all other endpoints: RATE_LIMIT_DEFAULT (applied globally via the middleware)
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _api_key_or_ip(request: Request) -> str:
    """Use X-API-Key as the rate-limit key; fall back to client IP."""
    key = request.headers.get("X-API-Key")
    if key:
        return key
    return get_remote_address(request)


limiter = Limiter(key_func=_api_key_or_ip, default_limits=[settings.rate_limit_default])
