import pytest

from src.infrastructure.adapters.media.ffmpeg_adapter import FFmpegProcessAdapter

PROBE_1080P = """ffmpeg version 7.1 Copyright (c) 2000-2025 the FFmpeg developers
  built with gcc 13.2.0 (Rev5, Built by MSYS2 project)
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'output.mp4':
  Metadata:
    major_brand     : isom
    minor_version   : 512
    compatible_brands: isomiso2mp41
    encoder         : Lavf60.3.100
  Duration: 00:03:32.54, start: 0.000000, bitrate: 1271 kb/s
  Stream #0:0[0x1](und): Video: av01 (av01 / 0x31307661), yuv420p(tv, bt709, progressive),
      1920x1080, 24 fps, 24 tbr, 90k tbn
  Stream #0:1[0x2](und): Audio: opus (Opus / 0x7375704F), 48000 Hz, stereo, fltp
"""

PROBE_MP3 = """ffmpeg version 7.1 Copyright (c) 2000-2025 the FFmpeg developers
Input #0, mp3, from 'audio.mp3':
  Metadata:
    encoder         : Lavf60.3.100
  Duration: 00:03:32.45, bitrate: 320 kb/s
  Stream #0:0: Audio: mp3, 48000 Hz, stereo, s16p, 320 kb/s
"""


def test_parse_probe_video_h264_1080p():
    result = FFmpegProcessAdapter.parse_probe_output(PROBE_1080P)
    assert result["format_name"] == "mov,mp4,m4a,3gp,3g2,mj2"
    assert result["duration_seconds"] == pytest.approx(212.54, abs=0.01)
    assert result["video"] == {"codec": "av01", "width": 1920, "height": 1080, "fps": 24.0}
    assert result["audio"]["codec"] == "opus"
    assert result["audio"]["sample_rate"] == 48000


def test_parse_probe_mp3():
    result = FFmpegProcessAdapter.parse_probe_output(PROBE_MP3)
    assert result["format_name"] == "mp3"
    assert result["video"] == {}
    assert result["audio"]["codec"] == "mp3"
    assert result["audio"]["sample_rate"] == 48000


def test_parse_probe_unreadable():
    result = FFmpegProcessAdapter.parse_probe_output("")
    assert "error" in result
