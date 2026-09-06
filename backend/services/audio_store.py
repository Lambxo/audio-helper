"""临时音频编号与文件的对应关系。

对外只返回 audio_id；内部用 index.json 记录创建时间与文件名，
供后续读取时做 24 小时有效期校验。读取时检查编号是否存在、是否过期。
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import get_settings

_index_lock = threading.Lock()

_MIME_BY_EXT = {
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
}


class AudioNotFound(Exception):
    """编号不存在、文件缺失或已超过 24 小时。"""


@dataclass(frozen=True)
class StoredAudio:
    audio_id: str
    data: bytes
    mime_type: str
    asr_text: str | None


def _root() -> Path:
    return Path(get_settings().storage_dir)


def audio_dir() -> Path:
    path = _root() / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _index_path() -> Path:
    return _root() / "index.json"


def _read_index() -> dict:
    path = _index_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_index(index: dict) -> None:
    path = _index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def new_audio_id() -> str:
    return f"aud_{uuid.uuid4().hex[:12]}"


def save_upload(audio_id: str, data: bytes, extension: str) -> None:
    """保存音频文件，并记录 created_at（UTC）。"""
    filename = f"{audio_id}{extension}"
    target = audio_dir() / filename
    target.write_bytes(data)
    record = {
        "kind": "upload",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
    }
    with _index_lock:
        index = _read_index()
        index[audio_id] = record
        _write_index(index)


def _parse_created_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_expired(created_at: datetime) -> bool:
    ttl = timedelta(hours=get_settings().audio_ttl_hours)
    return datetime.now(timezone.utc) - created_at > ttl


def load_upload(audio_id: str) -> StoredAudio:
    """按编号读取上传录音。不存在或过期时抛出 AudioNotFound，不把路径返回给调用方。"""
    with _index_lock:
        record = _read_index().get(audio_id)
    if not isinstance(record, dict) or record.get("kind") != "upload":
        raise AudioNotFound

    created_at = _parse_created_at(record.get("created_at"))
    if created_at is None or _is_expired(created_at):
        raise AudioNotFound

    filename = record.get("filename")
    if not isinstance(filename, str) or not filename:
        raise AudioNotFound

    path = audio_dir() / filename
    if not path.is_file():
        raise AudioNotFound

    mime_type = _MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream")
    cached = record.get("asr_text")
    asr_text = cached if isinstance(cached, str) and cached else None
    return StoredAudio(audio_id=audio_id, data=path.read_bytes(), mime_type=mime_type, asr_text=asr_text)


def save_asr_text(audio_id: str, text: str) -> None:
    with _index_lock:
        index = _read_index()
        record = index.get(audio_id)
        if not isinstance(record, dict):
            return
        record["asr_text"] = text
        index[audio_id] = record
        _write_index(index)
