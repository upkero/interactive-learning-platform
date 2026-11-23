"""HTTP request metrics exposed through Prometheus."""

from time import perf_counter

from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, make_asgi_app

HTTP_REQUESTS = Counter("http_requests", "HTTP requests by method, route and status", ["method", "route", "status"])
HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)


def register_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        started = perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        labels = {"method": request.method, "route": route_path}
        HTTP_REQUESTS.labels(**labels, status=str(response.status_code)).inc()
        HTTP_DURATION.labels(**labels).observe(perf_counter() - started)
        return response

    app.mount("/metrics", make_asgi_app())
