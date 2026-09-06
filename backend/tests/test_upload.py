"""POST /upload 接口测试。探测过程使用 mock，不调用真实 ffprobe，也不产生费用。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config import get_settings
from main import app
from services.audio_probe import ProbeError, ProbeResult


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield TestClient(app)
    get_settings.cache_clear()


def _ok_probe(_path):
    return ProbeResult(
        format_name="matroska,webm",
        codec_name="opus",
        duration_seconds=3.2,
        extension=".webm",
    )


def test_upload_success_returns_audio_id(client, tmp_path, monkeypatch):
    monkeypatch.setattr("api.upload.probe_audio", _ok_probe)

    response = client.post(
        "/upload",
        files={"file": ("meet-recording.webm", b"fake-webm-bytes", "audio/webm")},
    )

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body.get("request_id"), str) and body["request_id"]
    audio_id = body["data"]["audio_id"]
    assert audio_id.startswith("aud_")
    assert "/" not in audio_id and "\\" not in audio_id

    saved = tmp_path / "audio" / f"{audio_id}.webm"
    assert saved.is_file()
    assert saved.read_bytes() == b"fake-webm-bytes"

    index = Path(tmp_path / "index.json")
    assert index.is_file()
    text = index.read_text(encoding="utf-8")
    assert audio_id in text
    assert "created_at" in text
    assert str(saved) not in body["data"]["audio_id"]


def test_upload_unsupported_format_returns_415(client, monkeypatch):
    def reject(_path):
        raise ProbeError("AUDIO_FORMAT_UNSUPPORTED", "无法识别音频格式，请更换浏览器或重新录制")

    monkeypatch.setattr("api.upload.probe_audio", reject)
    response = client.post("/upload", files={"file": ("note.txt", b"not-audio", "text/plain")})

    assert response.status_code == 415
    error = response.json()["error"]
    assert error == {
        "code": "AUDIO_FORMAT_UNSUPPORTED",
        "message": "无法识别音频格式，请更换浏览器或重新录制",
        "stage": "upload",
    }


def test_upload_too_large_returns_413(client):
    payload = b"x" * (5 * 1024 * 1024 + 1)
    response = client.post("/upload", files={"file": ("huge.webm", payload, "audio/webm")})

    assert response.status_code == 413
    error = response.json()["error"]
    assert error["code"] == "AUDIO_TOO_LARGE"
    assert error["stage"] == "upload"
    assert error["message"] == "录音文件过大，请控制在5MB以内"


def test_upload_duration_invalid_returns_422(client, monkeypatch):
    def reject(_path):
        raise ProbeError("AUDIO_DURATION_INVALID", "录音时长需在1-60秒之间，当前约65.0秒")

    monkeypatch.setattr("api.upload.probe_audio", reject)
    response = client.post("/upload", files={"file": ("long.webm", b"fake", "audio/webm")})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "AUDIO_DURATION_INVALID"
    assert error["stage"] == "upload"


def test_upload_missing_file_returns_422(client):
    response = client.post("/upload")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["stage"] == "upload"
    assert "request_id" in body
