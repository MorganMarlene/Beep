import json
from pathlib import Path
from unittest.mock import patch

import pytest

from spotlight.media import MediaProbeError, parse_ffprobe_output, probe_video


def test_parse_ffprobe_output() -> None:
    output = json.dumps(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30000/1001",
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "125.5", "bit_rate": "4500000"},
        }
    )

    metadata = parse_ffprobe_output(output)

    assert metadata.duration_seconds == 125.5
    assert metadata.width == 1920
    assert metadata.height == 1080
    assert metadata.fps == pytest.approx(29.97, abs=0.001)
    assert metadata.video_codec == "h264"
    assert metadata.audio_codec == "aac"
    assert metadata.bitrate_bps == 4_500_000


def test_parse_ffprobe_output_rejects_missing_video_stream() -> None:
    output = json.dumps(
        {
            "streams": [{"codec_type": "audio", "codec_name": "aac"}],
            "format": {"duration": "1.0"},
        }
    )

    with pytest.raises(MediaProbeError):
        parse_ffprobe_output(output)


def test_probe_video_explains_how_to_install_missing_ffmpeg() -> None:
    with (
        patch("spotlight.media.subprocess.run", side_effect=FileNotFoundError),
        pytest.raises(MediaProbeError, match="Install FFmpeg"),
    ):
        probe_video(Path("video.mp4"))
