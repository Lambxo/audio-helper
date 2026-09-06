"""FastAPI 服务入口。"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api import api_router
from config import settings
from errors import new_request_id, register_exception_handlers

app = FastAPI(title="语音约碰面地点 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = new_request_id()
    return await call_next(request)


register_exception_handlers(app)
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=True)
