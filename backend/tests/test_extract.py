"""POST /extract：结构校验与业务完整性。默认 mock DeepSeek，不产生费用。"""

import json

import pytest
from fastapi.testclient import TestClient

from config import get_settings
from main import app
from services.extract import ExtractError, evaluate_business, parse_model_output


@pytest.fixture
def client(monkeypatch):
    get_settings.cache_clear()
    yield TestClient(app)
    get_settings.cache_clear()


NORMAL_MODEL = {
    "city_a": "杭州",
    "address_a": "杭州东站",
    "city_b": "杭州",
    "address_b": "西湖龙翔桥地铁站",
    "category": "咖啡店",
    "party_count": 2,
    "incomplete_reason": None,
}


def test_parse_rejects_invalid_json():
    with pytest.raises(ExtractError) as exc:
        parse_model_output("这不是JSON")
    assert exc.value.code == "EXTRACT_MODEL_BAD_OUTPUT"


def test_parse_rejects_missing_party_count():
    payload = dict(NORMAL_MODEL)
    payload.pop("party_count")
    with pytest.raises(ExtractError) as exc:
        parse_model_output(json.dumps(payload))
    assert exc.value.code == "EXTRACT_MODEL_BAD_OUTPUT"


def test_business_rejects_party_count():
    parsed = parse_model_output(
        json.dumps({**NORMAL_MODEL, "party_count": 3, "address_a": None, "address_b": None})
    )
    with pytest.raises(ExtractError) as exc:
        evaluate_business(parsed, "杭州")
    assert exc.value.code == "PARTY_COUNT_INVALID"


def test_business_rejects_vague_home_address():
    parsed = parse_model_output(
        json.dumps({**NORMAL_MODEL, "address_a": "我家", "address_b": "公司"})
    )
    with pytest.raises(ExtractError) as exc:
        evaluate_business(parsed, "杭州")
    assert exc.value.code == "ADDRESS_MISSING"


def test_business_rejects_cross_city():
    parsed = parse_model_output(
        json.dumps({**NORMAL_MODEL, "city_b": "上海", "address_b": "上海虹桥站"})
    )
    with pytest.raises(ExtractError) as exc:
        evaluate_business(parsed, "杭州")
    assert exc.value.code == "CROSS_CITY_NOT_SUPPORTED"


def test_business_normalizes_coffee_and_city_suffix():
    parsed = parse_model_output(
        json.dumps(
            {
                **NORMAL_MODEL,
                "city_a": "杭州市",
                "city_b": "杭州",
                "category": "喝咖啡",
            }
        )
    )
    result = evaluate_business(parsed, "杭州")
    assert result.category == "咖啡店"
    assert result.city_a == "杭州"
    assert result.model_dump().keys() == {
        "city_a",
        "address_a",
        "city_b",
        "address_b",
        "category",
    }


def test_business_uses_page_city_when_spoken_city_missing():
    parsed = parse_model_output(json.dumps({**NORMAL_MODEL, "city_a": None, "city_b": None}))
    result = evaluate_business(parsed, "杭州")
    assert result.city_a == "杭州"
    assert result.city_b == "杭州"


def test_extract_success_returns_five_fields(client, monkeypatch):
    async def fake_complete(text, city):
        return json.dumps(NORMAL_MODEL, ensure_ascii=False)

    monkeypatch.setattr("services.extract.complete_extract", fake_complete)
    response = client.post(
        "/extract",
        json={
            "text": "我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店。",
            "city": "杭州",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {
        "city_a": "杭州",
        "address_a": "杭州东站",
        "city_b": "杭州",
        "address_b": "西湖龙翔桥地铁站",
        "category": "咖啡店",
    }
    assert "party_count" not in data
    assert "incomplete_reason" not in data


def test_extract_missing_address_returns_422(client, monkeypatch):
    async def fake_complete(text, city):
        return json.dumps(
            {
                **NORMAL_MODEL,
                "address_b": None,
                "incomplete_reason": "缺少另一方地点",
            }
        )

    monkeypatch.setattr("services.extract.complete_extract", fake_complete)
    response = client.post("/extract", json={"text": "我在杭州东站，帮我找个咖啡店。", "city": "杭州"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ADDRESS_MISSING"


def test_extract_party_count_returns_422(client, monkeypatch):
    async def fake_complete(text, city):
        return json.dumps(
            {
                **NORMAL_MODEL,
                "address_a": None,
                "address_b": None,
                "party_count": 3,
                "incomplete_reason": "提到了三个人",
            }
        )

    monkeypatch.setattr("services.extract.complete_extract", fake_complete)
    response = client.post(
        "/extract",
        json={"text": "我、小李、小王三个人都在杭州，找个咖啡店碰面。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PARTY_COUNT_INVALID"


def test_extract_vague_address_returns_422(client, monkeypatch):
    async def fake_complete(text, city):
        return json.dumps({**NORMAL_MODEL, "address_a": "我家", "address_b": "公司"})

    monkeypatch.setattr("services.extract.complete_extract", fake_complete)
    response = client.post("/extract", json={"text": "我在我家，朋友在公司，找个咖啡店。", "city": "杭州"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "ADDRESS_MISSING"
    assert error["stage"] == "extract"


def test_extract_cross_city_returns_422(client, monkeypatch):
    async def fake_complete(text, city):
        return json.dumps({**NORMAL_MODEL, "city_b": "上海", "address_b": "上海虹桥站"})

    monkeypatch.setattr("services.extract.complete_extract", fake_complete)
    response = client.post(
        "/extract",
        json={"text": "我在杭州东站，朋友在上海虹桥站，找个中间的咖啡店。", "city": "杭州"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CROSS_CITY_NOT_SUPPORTED"


def test_extract_bad_model_json_returns_502(client, monkeypatch):
    async def fake_complete(text, city):
        return "好的，我理解了"

    monkeypatch.setattr("services.extract.complete_extract", fake_complete)
    response = client.post("/extract", json={"text": "随便说一句", "city": "杭州"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "EXTRACT_MODEL_BAD_OUTPUT"
    assert response.json()["error"]["message"] == "信息提取服务异常，请稍后重试"


def test_extract_timeout_returns_504(client, monkeypatch):
    async def fake_complete(text, city):
        raise ExtractError("DEEPSEEK_TIMEOUT", "信息提取超时，请稍后重试")

    monkeypatch.setattr("services.extract.complete_extract", fake_complete)
    response = client.post("/extract", json={"text": "我在杭州东站，朋友在龙翔桥。", "city": "杭州"})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "DEEPSEEK_TIMEOUT"


def test_deepseek_chat_url_defaults_to_beijing_compatible(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("BAILIAN_WORKSPACE_ID", raising=False)
    get_settings.cache_clear()
    try:
        from services.extract import deepseek_chat_url

        assert deepseek_chat_url() == (
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        )
    finally:
        get_settings.cache_clear()


def test_deepseek_chat_url_uses_workspace_id(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "llm-testspace")
    get_settings.cache_clear()
    try:
        from services.extract import deepseek_chat_url

        assert deepseek_chat_url() == (
            "https://llm-testspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions"
        )
    finally:
        get_settings.cache_clear()


def test_extract_missing_body_returns_422(client):
    response = client.post("/extract", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["stage"] == "extract"
