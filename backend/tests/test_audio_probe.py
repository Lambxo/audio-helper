"""音频探测：缺少 Duration 时应回退到数据包时间戳。"""

from pathlib import Path

import pytest

from services.audio_probe import ProbeError, probe_audio


def test_probe_uses_packet_timestamps_when_duration_missing(tmp_path, monkeypatch):
    audio = tmp_path / "clip.webm"
    audio.write_bytes(b"placeholder")

    def fake_run(args):
        if any("packet=" in str(item) for item in args):
            return {
                "packets": [
                    {"pts_time": "0.00", "duration_time": "0.02"},
                    {"pts_time": "3.10", "duration_time": "0.02"},
                ]
            }
        return {
            "format": {"format_name": "matroska,webm", "duration": "N/A"},
            "streams": [{"codec_type": "audio", "codec_name": "opus"}],
        }

    monkeypatch.setattr("services.audio_probe._run_ffprobe", fake_run)
    result = probe_audio(audio)
    assert result.duration_seconds == pytest.approx(3.12)
    assert result.extension == ".webm"
    assert result.codec_name == "opus"


def test_probe_rejects_duration_out_of_range(tmp_path, monkeypatch):
    audio = tmp_path / "clip.webm"
    audio.write_bytes(b"placeholder")

    monkeypatch.setattr(
        "services.audio_probe._run_ffprobe",
        lambda args: {
            "format": {"format_name": "webm", "duration": "65.0"},
            "streams": [{"codec_type": "audio", "codec_name": "opus"}],
        },
    )
    with pytest.raises(ProbeError) as exc:
        probe_audio(audio)
    assert exc.value.code == "AUDIO_DURATION_INVALID"


def test_probe_rejects_non_audio(tmp_path, monkeypatch):
    audio = tmp_path / "note.txt"
    audio.write_bytes(b"hello")

    monkeypatch.setattr(
        "services.audio_probe._run_ffprobe",
        lambda args: {
            "format": {"format_name": "txt"},
            "streams": [],
        },
    )
    with pytest.raises(ProbeError) as exc:
        probe_audio(audio)
    assert exc.value.code == "AUDIO_FORMAT_UNSUPPORTED"
