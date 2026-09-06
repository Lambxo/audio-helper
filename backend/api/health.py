"""健康检查接口：GET /health。"""

from fastapi import APIRouter, Request

from errors import get_request_id
from schemas import HealthData, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    return HealthResponse(
        request_id=get_request_id(request),
        data=HealthData(status="ok"),
    )
