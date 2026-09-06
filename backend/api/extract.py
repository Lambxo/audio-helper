"""地址与需求提取：POST /extract。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from errors import AppError, get_request_id
from schemas import ExtractData, ExtractRequest, ExtractResponse
from services.extract import ExtractError, extract_meeting

logger = logging.getLogger(__name__)

router = APIRouter()
STAGE = "extract"


def _map_extract_error(exc: ExtractError) -> AppError:
    status = {
        "ADDRESS_MISSING": 422,
        "PARTY_COUNT_INVALID": 422,
        "CROSS_CITY_NOT_SUPPORTED": 422,
        "EXTRACT_MODEL_BAD_OUTPUT": 502,
        "DEEPSEEK_TIMEOUT": 504,
    }.get(exc.code, 502)
    return AppError(status, exc.code, exc.message, STAGE)


@router.post("/extract", response_model=ExtractResponse)
async def extract_addresses(request: Request, body: ExtractRequest) -> ExtractResponse:
    request_id = get_request_id(request)
    if not body.text.strip() or not body.city.strip():
        raise AppError(422, "VALIDATION_ERROR", "请求缺少文件或字段类型不正确", STAGE)
    try:
        result = await extract_meeting(body.text.strip(), body.city.strip())
    except ExtractError as exc:
        logger.info("extract rejected: stage=extract code=%s", exc.code)
        raise _map_extract_error(exc) from exc
    return ExtractResponse(request_id=request_id, data=ExtractData.model_validate(result.model_dump()))
