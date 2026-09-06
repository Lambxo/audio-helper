"""上传录音：POST /upload。"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile

from config import get_settings
from errors import AppError, get_request_id
from schemas import UploadData, UploadResponse
from services.audio_probe import ProbeError, probe_audio
from services.audio_store import new_audio_id, save_upload

logger = logging.getLogger(__name__)

router = APIRouter()
STAGE = "upload"


def _map_probe_error(exc: ProbeError) -> AppError:
    status = {
        "AUDIO_FORMAT_UNSUPPORTED": 415,
        "AUDIO_DURATION_INVALID": 422,
        "AUDIO_PROBE_FAILED": 502,
    }.get(exc.code, 502)
    return AppError(status, exc.code, exc.message, STAGE)


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_audio(request: Request, file: UploadFile = File(...)) -> UploadResponse:
    settings = get_settings()
    request_id = get_request_id(request)
    declared_size = request.headers.get("content-length")
    if declared_size and declared_size.isdigit() and int(declared_size) > settings.max_audio_bytes + 4096:
        # multipart 包装会略大于原文件；明显超出时提前拒绝。
        raise AppError(413, "AUDIO_TOO_LARGE", "录音文件过大，请控制在5MB以内", STAGE)

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_audio_bytes:
            logger.info("upload rejected: stage=upload reason=too_large bytes=%s", total)
            raise AppError(413, "AUDIO_TOO_LARGE", "录音文件过大，请控制在5MB以内", STAGE)
        chunks.append(chunk)

    data = b"".join(chunks)
    if not data:
        raise AppError(415, "AUDIO_FORMAT_UNSUPPORTED", "无法识别音频格式，请更换浏览器或重新录制", STAGE)

    suffix = Path(file.filename or "upload").suffix or ".webm"
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        probe = probe_audio(tmp_path)
    except ProbeError as exc:
        logger.info("upload rejected: stage=upload code=%s", exc.code)
        raise _map_probe_error(exc) from exc
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    audio_id = new_audio_id()
    save_upload(audio_id, data, probe.extension)
    logger.info(
        "upload ok: stage=upload audio_id=%s duration_s=%.3f size=%s codec=%s",
        audio_id,
        probe.duration_seconds,
        total,
        probe.codec_name,
    )
    return UploadResponse(request_id=request_id, data=UploadData(audio_id=audio_id))
