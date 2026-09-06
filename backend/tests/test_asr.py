"""POST /asr 接口测试。默认 mock 百炼调用，不产生费用。"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config import get_settings
from main import app
from services.audio_store import save_upload
from services.bailian_asr import AsrError


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield TestClient(app)
    get_settings.cache_clear()


def _seed_audio(audio_id: str = "aud_testhappy1") -> str:
    save_upload(audio_id, b"fake-webm-bytes", ".webm")
    return audio_id


def test_asr_success_returns_text(client, monkeypatch):
    audio_id = _seed_audio()

    async def fake_transcribe(data, mime_type):
        assert data == b"fake-webm-bytes"
        assert mime_type == "audio/webm"
        return "我在杭州东站，朋友在西湖龙翔桥地铁站，帮我们找个中间的咖啡店。"

    monkeypatch.setattr("api.asr.transcribe", fake_transcribe)
    response = client.post("/asr", json={"audio_id": audio_id})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("request_id"), str) and body["request_id"]
    assert body["data"]["text"].startswith("我在杭州东站")


def test_asr_unknown_id_returns_404(client, monkeypatch):
    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("expired or missing id must not call ASR")

    monkeypatch.setattr("api.asr.transcribe", fail_if_called)
    response = client.post("/asr", json={"audio_id": "aud_doesnotexist"})
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "AUDIO_ID_NOT_FOUND",
        "message": "录音已过期，请重新录制",
        "stage": "asr",
    }


def test_asr_expired_id_returns_404(client, tmp_path, monkeypatch):
    audio_id = _seed_audio("aud_expired0001")
    index_path = Path(tmp_path) / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index[audio_id]["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    index_path.write_text(json.dumps(index), encoding="utf-8")

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("expired id must not call ASR")

    monkeypatch.setattr("api.asr.transcribe", fail_if_called)
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_ID_NOT_FOUND"


def test_asr_empty_result_returns_422(client, monkeypatch):
    audio_id = _seed_audio("aud_emptyresult")

    async def empty(_data, _mime):
        raise AsrError("ASR_EMPTY_RESULT", "没有识别到有效语音，请重新说一遍")

    monkeypatch.setattr("api.asr.transcribe", empty)
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "ASR_EMPTY_RESULT",
        "message": "没有识别到有效语音，请重新说一遍",
        "stage": "asr",
    }


def test_asr_timeout_returns_504(client, monkeypatch):
    audio_id = _seed_audio("aud_timeout0001")

    async def timeout(_data, _mime):
        raise AsrError("ASR_TIMEOUT", "语音识别超时，请稍后重试")

    monkeypatch.setattr("api.asr.transcribe", timeout)
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "ASR_TIMEOUT"
    assert response.json()["error"]["stage"] == "asr"


def test_asr_vendor_error_returns_502(client, monkeypatch):
    audio_id = _seed_audio("aud_badresp0001")

    async def bad(_data, _mime):
        raise AsrError("ASR_BAD_RESPONSE", "语音识别服务异常，请稍后重试")

    monkeypatch.setattr("api.asr.transcribe", bad)
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ASR_BAD_RESPONSE"


def test_asr_missing_field_returns_422(client):
    response = client.post("/asr", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["stage"] == "asr"


def test_asr_uses_cache_and_does_not_call_vendor_twice(client, monkeypatch):
    audio_id = _seed_audio("aud_cacheonce01")
    calls = {"n": 0}

    async def once(_data, _mime):
        calls["n"] += 1
        return "只应识别一次"

    monkeypatch.setattr("api.asr.transcribe", once)
    first = client.post("/asr", json={"audio_id": audio_id})
    second = client.post("/asr", json={"audio_id": audio_id})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["text"] == "只应识别一次"
    assert calls["n"] == 1
