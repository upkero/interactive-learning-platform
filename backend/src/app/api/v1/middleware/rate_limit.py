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


def client_ip(request: Request) -> str:
    """Client IP behind the nginx proxy.

    ``request.client`` is the proxy itself, so without the forwarded
    header all users would share one rate bucket. The header is
    trustworthy here: nginx overwrites it with the real client address.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Answer 429 in the unified error format instead of slowapi's plain text."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests.", "error_code": "rate_limited"},
    )


def register_rate_limit(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, cast(Any, rate_limit_exceeded_handler))
