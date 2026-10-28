from collections.abc import Mapping
from logging import getLogger
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.app.exceptions.base import BaseAppException

logger = getLogger(__name__)


def _error_response(
    status: int,
    detail: Any,
    error_code: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    # Cast to dict: JSONResponse requires dict headers
    resp_headers = dict(headers) if headers else None
    return JSONResponse(
        status_code=status,
        content={"detail": detail, "error_code": error_code},
        headers=resp_headers,
    )


async def handle_app_exception(request: Request, exc: BaseAppException) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error(
            "Application error on %s %s: %s",
            request.method,
            request.url.path,
            exc.detail,
            exc_info=exc,
        )
    return _error_response(exc.status_code, exc.detail, exc.error_code)


async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Request validation error on %s %s", request.method, request.url.path)
    errors = exc.errors()
    for err in errors:
        if (ctx := err.get("ctx")) and isinstance(ctx.get("error"), Exception):
            ctx["error"] = str(ctx["error"])
    return _error_response(422, errors, "request_validation_error")


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(exc.status_code, exc.detail, "http_error", headers=exc.headers)


async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return _error_response(500, "Internal server error", "internal_server_error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BaseAppException, cast(Any, handle_app_exception))
    app.add_exception_handler(RequestValidationError, cast(Any, handle_request_validation_error))
    app.add_exception_handler(StarletteHTTPException, cast(Any, handle_http_exception))
    app.add_exception_handler(Exception, handle_unexpected_exception)
