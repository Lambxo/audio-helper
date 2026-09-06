"""百炼 ASR 请求构造与响应解析。不发起真实网络调用。"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from config import get_settings
from services.bailian_asr import AsrError, _extract_text, transcribe


def test_extract_text_from_dashscope_message_list():
    payload = {
        "output": {
            "choices": [
                {"message": {"content": [{"text": "  欢迎使用阿里云。  "}]}}
            ]
        }
    }
    assert _extract_text(payload) == "  欢迎使用阿里云。  "


def test_extract_text_missing_fields_is_none():
    assert _extract_text({"output": {}}) is None
    assert _extract_text("not-json-object") is None


def test_transcribe_rejects_oversized_data_uri(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "sk-test")
    monkeypatch.setenv("MAX_ASR_DATA_URI_BYTES", "32")
    get_settings.cache_clear()
    try:
        with pytest.raises(AsrError) as exc:
            asyncio.run(transcribe(b"0123456789abcdef", "audio/webm"))
        assert exc.value.code == "ASR_PAYLOAD_TOO_LARGE"
    finally:
        get_settings.cache_clear()


def test_transcribe_maps_timeout(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "sk-test")
    get_settings.cache_clear()

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("timeout")
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    try:
        with patch("services.bailian_asr.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AsrError) as exc:
                asyncio.run(transcribe(b"abc", "audio/webm"))
        assert exc.value.code == "ASR_TIMEOUT"
    finally:
        get_settings.cache_clear()


def test_transcribe_maps_connect_error(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "sk-test")
    get_settings.cache_clear()

    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("ssl eof")
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    try:
        with patch("services.bailian_asr.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AsrError) as exc:
                asyncio.run(transcribe(b"abc", "audio/webm"))
        assert exc.value.code == "ASR_BAD_RESPONSE"
        assert "无法连接" in exc.value.message
    finally:
        get_settings.cache_clear()


def test_transcribe_maps_http_401(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "sk-test")
    get_settings.cache_clear()

    response = Mock()
    response.status_code = 401
    response.json.return_value = {"code": "InvalidApiKey", "message": "Invalid API-key provided."}

    mock_client = AsyncMock()
    mock_client.post.return_value = response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    try:
        with patch("services.bailian_asr.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AsrError) as exc:
                asyncio.run(transcribe(b"abc", "audio/webm"))
        assert exc.value.code == "ASR_BAD_RESPONSE"
        assert "鉴权失败" in exc.value.message
        assert "InvalidApiKey" in exc.value.message
    finally:
        get_settings.cache_clear()


def test_transcribe_maps_vendor_code_on_http_200(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "sk-test")
    get_settings.cache_clear()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {"code": "InvalidApiKey", "message": "Invalid API-key provided."}

    mock_client = AsyncMock()
    mock_client.post.return_value = response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    try:
        with patch("services.bailian_asr.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AsrError) as exc:
                asyncio.run(transcribe(b"abc", "audio/webm"))
        assert exc.value.code == "ASR_BAD_RESPONSE"
        assert "鉴权失败" in exc.value.message
    finally:
        get_settings.cache_clear()


def test_transcribe_maps_empty_text(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "sk-test")
    get_settings.cache_clear()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "output": {"choices": [{"message": {"content": [{"text": "   "}]}}]}
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    try:
        with patch("services.bailian_asr.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AsrError) as exc:
                asyncio.run(transcribe(b"abc", "audio/webm"))
        assert exc.value.code == "ASR_EMPTY_RESULT"
    finally:
        get_settings.cache_clear()
