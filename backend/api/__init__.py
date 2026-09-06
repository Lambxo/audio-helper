"""接口路由聚合。

各接口模块（health.py、后续的 upload.py / asr.py / extract.py /
search.py / finalize.py / audio.py）分别定义自己的 router，
在此统一注册，main.py 只需要 include 这一个聚合路由。
"""

from fastapi import APIRouter

from .health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
