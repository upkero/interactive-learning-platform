"""Rate limiting via slowapi: shared Limiter, unified 429 error format.

Endpoints opt in with ``@limiter.limit("10/minute")`` (the decorator
requires a ``request: Request`` parameter on the endpoint function).
The key is the client IP: authentication (and per-user limits) comes
with story 1.4.2, while registration and login must be capped before
that.
"""

from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from src.app.core.settings.rate_limit import get_rate_limit_settings
from src.app.exceptions.auth import RateLimitedError


def client_ip(request: Request) -> str:
    """Client IP behind the nginx proxy.

    Nginx overwrites X-Real-IP; X-Forwarded-For may contain client-supplied
    values and must not be used for the rate-limit key. API access must be
    restricted to trusted proxies in production.
    """
    forwarded = request.headers.get("x-real-ip")
    if forwarded and forwarded.strip():
        return forwarded.strip()
    return get_remote_address(request)


# The decorators need this limiter at import time, before the container exists.
limiter = Limiter(
    key_func=client_ip,
    storage_uri=get_rate_limit_settings().storage_uri,
    key_prefix="grasp:ratelimit",
    in_memory_fallback_enabled=True,
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Answer 429 in the unified error format instead of slowapi's plain text."""
    error = RateLimitedError()
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail, "error_code": error.error_code})


def register_rate_limit(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, cast(Any, rate_limit_exceeded_handler))
