"""请求编号与统一错误结构。"""

from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or new_request_id()


def stage_from_path(path: str) -> str:
    if path.startswith("/upload"):
        return "upload"
    if path.startswith("/asr"):
        return "asr"
    if path.startswith("/extract"):
        return "extract"
    if path.startswith("/search"):
        return "search"
    if path.startswith("/finalize"):
        return "finalize"
    if path.startswith("/audio"):
        return "audio_download"
    return "unknown"


class AppError(Exception):
    """业务或校验失败，由全局处理器转成约定的 JSON 错误。"""

    def __init__(self, status_code: int, code: str, message: str, stage: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.stage = stage
        super().__init__(message)


def error_body(request_id: str, code: str, message: str, stage: str) -> dict:
    return {
        "request_id": request_id,
        "error": {
            "code": code,
            "message": message,
            "stage": stage,
        },
    }


def register_exception_handlers(app) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(get_request_id(request), exc.code, exc.message, exc.stage),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body(
                get_request_id(request),
                "VALIDATION_ERROR",
                "请求缺少文件或字段类型不正确",
                stage_from_path(request.url.path),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        message = exc.detail if isinstance(exc.detail, str) else "请求无法处理"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                get_request_id(request),
                "HTTP_ERROR",
                message,
                stage_from_path(request.url.path),
            ),
        )
