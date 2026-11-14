from fastapi import APIRouter

from src.app.api.v1.routers.auth import router as auth_router
from src.app.api.v1.routers.documents import router as documents_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(documents_router)
