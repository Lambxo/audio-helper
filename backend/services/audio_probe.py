"""用 ffprobe 探测真实容器、编码和时长。探测不等于转码。

浏览器 WebM 经常缺少 format.duration；此时改用音频包时间戳，
不把缺少 Duration 直接判为非法。
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from config import get_settings

logger = logging.getLogger(__name__)

ALLOWED_FORMAT_TOKENS = frozenset({"webm", "matroska", "ogg", "wav", "mp3", "mpeg"})
ALLOWED_CODEC_PREFIXES = ("opus", "vorbis", "aac", "mp3", "pcm")


class ProbeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ProbeResult:
    format_name: str
    codec_name: str
    duration_seconds: float
    extension: str


def _ffprobe_bin() -> str:
    configured = get_settings().ffprobe_path
    if Path(configured).is_file():
        return configured
    found = shutil.which(configured)
    if found:
        return found
    raise ProbeError(
        "AUDIO_PROBE_FAILED",
        "无法探测音频：未找到 ffprobe。请安装 FFmpeg 并将 ffprobe 加入 PATH 后重试",
    )


def _run_ffprobe(args: list[str]) -> dict:
    timeout = max(1.0, get_settings().upload_timeout_s - 1.0)
    command = [_ffprobe_bin(), "-v", "error", *args]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("AUDIO_PROBE_FAILED", "音频探测超时，请稍后重试") from exc
    except OSError as exc:
        raise ProbeError("AUDIO_PROBE_FAILED", "无法启动音频探测工具") from exc

    if completed.returncode != 0:
        logger.info("ffprobe failed: returncode=%s", completed.returncode)
        raise ProbeError("AUDIO_FORMAT_UNSUPPORTED", "无法识别音频格式，请更换浏览器或重新录制")

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ProbeError("AUDIO_PROBE_FAILED", "音频探测结果无法解析") from exc
    if not isinstance(payload, dict):
        raise ProbeError("AUDIO_PROBE_FAILED", "音频探测结果无法解析")
    return payload


def _parse_optional_float(value: object) -> float | None:
    if value is None or value == "" or value == "N/A":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number < 0:  # NaN or negative
        return None
    return number


def _duration_from_format(info: dict) -> float | None:
    fmt = info.get("format") or {}
    return _parse_optional_float(fmt.get("duration"))


def _duration_from_packets(path: Path) -> float | None:
    info = _run_ffprobe(
        [
            "-select_streams",
            "a:0",
            "-show_entries",
            "packet=pts_time,duration_time",
            "-of",
            "json",
            str(path),
        ]
    )
    packets = info.get("packets") or []
    last_pts: float | None = None
    last_packet_duration: float | None = None
    for packet in packets:
        pts = _parse_optional_float(packet.get("pts_time"))
        if pts is None:
            continue
        last_pts = pts
        last_packet_duration = _parse_optional_float(packet.get("duration_time"))
    if last_pts is None:
        return None
    if last_packet_duration is not None:
        return last_pts + last_packet_duration
    return last_pts


def _pick_audio_stream(info: dict) -> dict | None:
    for stream in info.get("streams") or []:
        if stream.get("codec_type") == "audio":
            return stream
    return None


def _format_allowed(format_name: str) -> bool:
    tokens = {token.strip().lower() for token in format_name.split(",") if token.strip()}
    return bool(tokens & ALLOWED_FORMAT_TOKENS)


def _codec_allowed(codec_name: str) -> bool:
    lowered = codec_name.lower()
    return any(lowered.startswith(prefix) for prefix in ALLOWED_CODEC_PREFIXES)


def _extension_for(format_name: str) -> str:
    lowered = format_name.lower()
    if "webm" in lowered:
        return ".webm"
    if "ogg" in lowered:
        return ".ogg"
    if "wav" in lowered:
        return ".wav"
    if "mp3" in lowered or "mpeg" in lowered:
        return ".mp3"
    return ".webm"


def probe_audio(path: Path) -> ProbeResult:
    info = _run_ffprobe(
        [
            "-analyzeduration",
            "20M",
            "-probesize",
            "20M",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
    )

    format_name = str((info.get("format") or {}).get("format_name") or "")
    if not format_name or not _format_allowed(format_name):
        raise ProbeError("AUDIO_FORMAT_UNSUPPORTED", "无法识别音频格式，请更换浏览器或重新录制")

    audio_stream = _pick_audio_stream(info)
    codec_name = str((audio_stream or {}).get("codec_name") or "")
    if audio_stream is None or not _codec_allowed(codec_name):
        raise ProbeError("AUDIO_FORMAT_UNSUPPORTED", "无法识别音频格式，请更换浏览器或重新录制")

    duration = _duration_from_format(info)
    if duration is None:
        logger.info("format duration missing, falling back to packet timestamps")
        duration = _duration_from_packets(path)
    if duration is None:
        raise ProbeError("AUDIO_PROBE_FAILED", "无法从音频流中读取时长，请重新录制")

    settings = get_settings()
    if duration < settings.min_audio_duration_s or duration > settings.max_audio_duration_s:
        raise ProbeError(
            "AUDIO_DURATION_INVALID",
            f"录音时长需在1-60秒之间，当前约{duration:.1f}秒",
        )

    return ProbeResult(
        format_name=format_name,
        codec_name=codec_name,
        duration_seconds=duration,
        extension=_extension_for(format_name),
    )
