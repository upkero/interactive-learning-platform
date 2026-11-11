from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.api.v1.exception_handlers import register_exception_handlers
from src.app.api.v1.middleware.rate_limit import register_rate_limit
from src.app.api.v1.middleware.request_id import register_request_id_middleware
from src.app.api.v1.router import api_router
from src.app.api.v1.routers.health import router as health_router
from src.app.bootstrap.container import ApplicationContainer
from src.app.core.logging import setup_logging
from src.app.core.settings.app import get_app_settings
from src.app.core.settings.auth import get_auth_settings
from src.app.core.settings.logging import get_logging_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    container = ApplicationContainer()
    app.state.container = container
    try:
        yield
    finally:
        await container.close()


def create_app() -> FastAPI:
    setup_logging(get_logging_settings())

    # Validate required secrets at startup (DoD 1.1.4)
    get_auth_settings()

    app = FastAPI(
        title="Grasp API",
        version="0.1.0",
        lifespan=lifespan,
        # All tag groups of the API, so /docs shows the full outline even
        # while some areas are not implemented yet (stories 1.4.*).
        openapi_tags=[
            {"name": "infra", "description": "Liveness and readiness."},
            {"name": "auth", "description": "Registration, login, logout; session cookie."},
            {"name": "documents", "description": "Upload, import, topics, plan, generate."},
            {"name": "parts", "description": "Page content of a part."},
            {"name": "quiz-attempts", "description": "Answers to quiz tasks."},
            {"name": "widgets", "description": "Widget reports."},
            {"name": "materials", "description": "Sharing materials by email."},
            {"name": "me", "description": "Profile, materials, quota."},
        ],
    )

    settings = get_app_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials="*" not in settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_request_id_middleware(app)
    register_rate_limit(app)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
