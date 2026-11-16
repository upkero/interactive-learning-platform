from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from src.app.api.v1.exception_handlers import handle_unexpected_exception
from src.app.core.request_id import generate_request_id, set_request_id

_HEADER = "X-Request-ID"
_SKIP_PATHS = frozenset({"/metrics", "/health/live", "/health/ready"})


def register_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)
        request_id = request.headers.get(_HEADER) or generate_request_id()
        request.state.request_id = request_id
        set_request_id(request_id)
        try:
            response: Response = await call_next(request)
        except Exception as exc:
            # Handle unexpected errors while the request context is still
            # available instead of letting the server log a second traceback.
            response = await handle_unexpected_exception(request, exc)
        response.headers[_HEADER] = request_id
        return response
