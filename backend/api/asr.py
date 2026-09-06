"""语音识别：POST /asr。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from errors import AppError, get_request_id
from schemas import AsrData, AsrRequest, AsrResponse
from services.audio_store import AudioNotFound, load_upload, save_asr_text
from services.bailian_asr import AsrError, transcribe

logger = logging.getLogger(__name__)

router = APIRouter()
STAGE = "asr"


def _map_asr_error(exc: AsrError) -> AppError:
    status = {
        "ASR_EMPTY_RESULT": 422,
        "ASR_BAD_RESPONSE": 502,
        "ASR_TIMEOUT": 504,
        "ASR_PAYLOAD_TOO_LARGE": 502,
    }.get(exc.code, 502)
    return AppError(status, exc.code, exc.message, STAGE)


@router.post("/asr", response_model=AsrResponse)
async def asr_audio(request: Request, body: AsrRequest) -> AsrResponse:
    request_id = get_request_id(request)
    try:
        stored = load_upload(body.audio_id)
    except AudioNotFound as exc:
        raise AppError(404, "AUDIO_ID_NOT_FOUND", "录音已过期，请重新录制", STAGE) from exc

    if stored.asr_text:
        logger.info("asr cache hit: stage=asr audio_id=%s", stored.audio_id)
        return AsrResponse(request_id=request_id, data=AsrData(text=stored.asr_text))

    try:
        text = await transcribe(stored.data, stored.mime_type)
    except AsrError as exc:
        logger.info("asr rejected: stage=asr code=%s", exc.code)
        raise _map_asr_error(exc) from exc

    save_asr_text(stored.audio_id, text)
    return AsrResponse(request_id=request_id, data=AsrData(text=text))
