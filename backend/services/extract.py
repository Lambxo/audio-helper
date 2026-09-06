"""调用 DeepSeek 提取碰面双方城市、地址和类别。

先用 Pydantic 校验模型 JSON 结构，再判断业务完整性。
非法 JSON / 缺字段 / 类型错误视为模型输出异常（502），不能解释成用户没说清楚。
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from config import get_settings
from prompts import load_extract_prompt

logger = logging.getLogger(__name__)

VAGUE_ADDRESSES = frozenset({"我家", "家", "公司", "单位", "这里", "那里", "我家附近", "公司附近"})
CATEGORY_ALIASES = {
    "喝咖啡": "咖啡店",
    "咖啡": "咖啡店",
    "咖啡馆": "咖啡店",
}


class ExtractError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ModelExtractOutput(BaseModel):
    """模型内部约定字段，全部必须出现。"""

    model_config = ConfigDict(extra="ignore")

    city_a: str | None
    address_a: str | None
    city_b: str | None
    address_b: str | None
    category: str | None
    party_count: int
    incomplete_reason: str | None


class ExtractBusinessResult(BaseModel):
    city_a: str
    address_a: str
    city_b: str
    address_b: str
    category: str


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_city(value: str | None) -> str | None:
    city = _blank_to_none(value)
    if city is None:
        return None
    if city.endswith("市") and len(city) > 1:
        return city[:-1]
    return city


def _normalize_address(value: str | None) -> str | None:
    address = _blank_to_none(value)
    if address is None:
        return None
    if address in VAGUE_ADDRESSES:
        return None
    return address


def _normalize_category(value: str | None) -> str:
    category = _blank_to_none(value)
    if category is None:
        return "咖啡店"
    return CATEGORY_ALIASES.get(category, category)


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    return text


def parse_model_output(raw: str) -> ModelExtractOutput:
    try:
        payload = json.loads(_strip_fence(raw))
    except json.JSONDecodeError as exc:
        raise ExtractError("EXTRACT_MODEL_BAD_OUTPUT", "信息提取服务异常，请稍后重试") from exc
    try:
        return ModelExtractOutput.model_validate(payload)
    except ValidationError as exc:
        raise ExtractError("EXTRACT_MODEL_BAD_OUTPUT", "信息提取服务异常，请稍后重试") from exc


def evaluate_business(parsed: ModelExtractOutput, default_city: str) -> ExtractBusinessResult:
    city_a = _normalize_city(parsed.city_a) or _normalize_city(default_city)
    city_b = _normalize_city(parsed.city_b) or _normalize_city(default_city)
    address_a = _normalize_address(parsed.address_a)
    address_b = _normalize_address(parsed.address_b)
    category = _normalize_category(parsed.category)

    if parsed.party_count != 2:
        raise ExtractError("PARTY_COUNT_INVALID", "目前仅支持两个人碰面，请只描述两人的位置")

    if address_a is None or address_b is None or city_a is None or city_b is None:
        raise ExtractError("ADDRESS_MISSING", "没听清其中一方的地点，请重新描述两人的具体位置")

    if city_a != city_b:
        raise ExtractError("CROSS_CITY_NOT_SUPPORTED", "暂不支持跨城市找店，请确认两人是否在同一座城市")

    return ExtractBusinessResult(
        city_a=city_a,
        address_a=address_a,
        city_b=city_b,
        address_b=address_b,
        category=category,
    )


def deepseek_chat_url() -> str:
    settings = get_settings()
    configured = settings.deepseek_base_url.strip()
    if configured:
        url = configured.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        return f"{url}/chat/completions"
    workspace = settings.bailian_workspace_id.strip()
    if not workspace:
        raise ExtractError(
            "EXTRACT_MODEL_BAD_OUTPUT",
            "信息提取服务未配置调用地址，请填写 BAILIAN_WORKSPACE_ID 或 DEEPSEEK_BASE_URL",
        )
    return (
        f"https://{workspace}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions"
    )


def _message_content(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None


async def complete_extract(text: str, city: str) -> str:
    """调用 DeepSeek，返回模型原始 content 字符串（尚未做业务裁剪）。"""
    settings = get_settings()
    if not settings.bailian_api_key:
        raise ExtractError("EXTRACT_MODEL_BAD_OUTPUT", "信息提取服务未配置密钥，请在 backend/.env 填写 BAILIAN_API_KEY")

    url = deepseek_chat_url()
    body = {
        "model": settings.deepseek_model,
        "enable_thinking": False,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": load_extract_prompt()},
            {"role": "user", "content": json.dumps({"text": text, "city": city}, ensure_ascii=False)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.bailian_api_key}",
        "Content-Type": "application/json",
    }

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.extract_timeout_s) as client:
            response = await client.post(url, json=body, headers=headers)
    except httpx.TimeoutException as exc:
        logger.info("extract timeout: stage=extract elapsed_ms=%s", int((time.perf_counter() - started) * 1000))
        raise ExtractError("DEEPSEEK_TIMEOUT", "信息提取超时，请稍后重试") from exc
    except httpx.HTTPError as exc:
        logger.info("extract http error: stage=extract")
        raise ExtractError("EXTRACT_MODEL_BAD_OUTPUT", "信息提取服务异常，请稍后重试") from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info("extract vendor response: stage=extract http_status=%s elapsed_ms=%s", response.status_code, elapsed_ms)

    if response.status_code >= 400:
        raise ExtractError("EXTRACT_MODEL_BAD_OUTPUT", "信息提取服务异常，请稍后重试")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ExtractError("EXTRACT_MODEL_BAD_OUTPUT", "信息提取服务异常，请稍后重试") from exc

    content = _message_content(payload)
    if content is None:
        raise ExtractError("EXTRACT_MODEL_BAD_OUTPUT", "信息提取服务异常，请稍后重试")
    logger.info("extract model content chars=%s", len(content))
    return content


async def extract_meeting(text: str, city: str) -> ExtractBusinessResult:
    raw = await complete_extract(text, city)
    parsed = parse_model_output(raw)
    logger.info(
        "extract parsed: stage=extract party_count=%s incomplete_reason=%s",
        parsed.party_count,
        parsed.incomplete_reason,
    )
    return evaluate_business(parsed, city)
