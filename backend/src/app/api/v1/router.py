from fastapi import APIRouter

from src.app.api.v1.routers.auth import router as auth_router
from src.app.api.v1.routers.documents import router as documents_router
from src.app.api.v1.routers.events import router as events_router
from src.app.api.v1.routers.materials import router as materials_router
from src.app.api.v1.routers.me import router as me_router
from src.app.api.v1.routers.parts import router as parts_router
from src.app.api.v1.routers.quiz_attempts import router as quiz_attempts_router
from src.app.api.v1.routers.widgets import router as widgets_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(events_router)
api_router.include_router(materials_router)
api_router.include_router(me_router)
api_router.include_router(parts_router)
api_router.include_router(quiz_attempts_router)
api_router.include_router(widgets_router)
