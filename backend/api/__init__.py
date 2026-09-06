"""接口路由聚合。"""

from fastapi import APIRouter

from .health import router as health_router
from .upload import router as upload_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(upload_router)
