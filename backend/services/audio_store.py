"""临时音频编号与文件的对应关系。

对外只返回 audio_id；内部用 index.json 记录创建时间与文件名，
供后续读取时做 24 小时有效期校验。本轮 /upload 只写入，不对外暴露路径。
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import get_settings

_index_lock = threading.Lock()


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
