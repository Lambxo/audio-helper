"""健康检查接口：GET /health。

不依赖任何外部服务（百炼 / DeepSeek / 高德），因此即使未配置
任何密钥，本接口也应始终返回 200。
"""

import uuid

from fastapi import APIRouter

from schemas import HealthData, HealthResponse

router = APIRouter()


def _new_request_id() -> str:
    """生成本次请求的编号，形如 req_1a2b3c4d5e6f。"""
    return f"req_{uuid.uuid4().hex[:12]}"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        request_id=_new_request_id(),
        data=HealthData(status="ok"),
    )
