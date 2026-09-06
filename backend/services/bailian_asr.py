"""调用百炼 qwen3-asr-flash（北京地域 DashScope 同步接口）。

不在日志中输出 API Key 或音频 Base64。
"""

from __future__ import annotations

import base64
import logging
import time

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


class AsrError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _extract_text(payload: object) -> str | None:
    """从供应商 JSON 取出识别文字。字段缺失返回 None（模型输出异常），空字符串表示识别为空。"""
    if not isinstance(payload, dict):
        return None
    output = payload.get("output")
    if not isinstance(output, dict):
        return None
    choices = output.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list) and content:
        item = content[0]
        if isinstance(item, dict) and "text" in item:
            text = item.get("text")
            return text if isinstance(text, str) else None
        if isinstance(item, str):
            return item
    return None


async def transcribe(audio_bytes: bytes, mime_type: str) -> str:
    settings = get_settings()
    if not settings.bailian_api_key:
        raise AsrError("ASR_BAD_RESPONSE", "语音识别服务未配置密钥，请在 backend/.env 填写 BAILIAN_API_KEY")

    encoded = base64.b64encode(audio_bytes).decode("ascii")
    data_uri = f"data:{mime_type};base64,{encoded}"
    if len(data_uri.encode("utf-8")) > settings.max_asr_data_uri_bytes:
        raise AsrError("ASR_PAYLOAD_TOO_LARGE", "音频编码后超出识别服务限制，请缩短录音后重试")

    body = {
        "model": settings.asr_model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"audio": data_uri}],
                }
            ]
        },
        "parameters": {"asr_options": {"enable_itn": False}},
    }
    headers = {
        "Authorization": f"Bearer {settings.bailian_api_key}",
        "Content-Type": "application/json",
    }

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.asr_timeout_s) as client:
            response = await client.post(settings.asr_base_url, json=body, headers=headers)
    except httpx.TimeoutException as exc:
        logger.info("asr timeout: stage=asr elapsed_ms=%s", int((time.perf_counter() - started) * 1000))
        raise AsrError("ASR_TIMEOUT", "语音识别超时，请稍后重试") from exc
    except httpx.HTTPError as exc:
        logger.info("asr http error: stage=asr")
        raise AsrError("ASR_BAD_RESPONSE", "语音识别服务异常，请稍后重试") from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info("asr vendor response: stage=asr http_status=%s elapsed_ms=%s", response.status_code, elapsed_ms)

    if response.status_code >= 500:
        raise AsrError("ASR_BAD_RESPONSE", "语音识别服务异常，请稍后重试")
    if response.status_code == 429:
        raise AsrError("ASR_BAD_RESPONSE", "语音识别服务繁忙，请稍后重试")
    if response.status_code >= 400:
        raise AsrError("ASR_BAD_RESPONSE", "语音识别服务异常，请稍后重试")

    try:
        payload = response.json()
    except ValueError as exc:
        raise AsrError("ASR_BAD_RESPONSE", "语音识别服务异常，请稍后重试") from exc

    text = _extract_text(payload)
    if text is None:
        raise AsrError("ASR_BAD_RESPONSE", "语音识别服务异常，请稍后重试")
    stripped = text.strip()
    if not stripped:
        raise AsrError("ASR_EMPTY_RESULT", "没有识别到有效语音，请重新说一遍")
    logger.info("asr ok: stage=asr text_chars=%s elapsed_ms=%s", len(stripped), elapsed_ms)
    return stripped
