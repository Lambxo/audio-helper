"""FastAPI 服务入口。

本轮只挂载 /health。CORS 只放行 config.py 中配置的前端地址
（默认 http://localhost:5175），不使用通配符。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import api_router
from config import settings

app = FastAPI(title="语音约碰面地点 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=True)
