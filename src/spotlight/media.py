"""Video metadata inspection using ffprobe."""

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


class MediaProbeError(Exception):
    """Raised when video metadata cannot be read."""


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """The video details displayed by Spotlight."""

    duration_seconds: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    bitrate_bps: int


def parse_ffprobe_output(output: str) -> VideoMetadata:
    """Parse ffprobe's JSON output into displayable video metadata."""
    try:
        data: dict[str, Any] = json.loads(output)
        streams: list[dict[str, Any]] = data["streams"]
        format_data: dict[str, Any] = data["format"]
        video_stream = next(
            stream for stream in streams if stream.get("codec_type") == "video"
        )
        audio_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"),
            None,
        )

        frame_rate = video_stream.get("avg_frame_rate") or video_stream.get(
            "r_frame_rate"
        )
        fps = float(Fraction(str(frame_rate)))
        bitrate = format_data.get("bit_rate") or video_stream.get("bit_rate") or 0

        return VideoMetadata(
            duration_seconds=float(format_data["duration"]),
            width=int(video_stream["width"]),
            height=int(video_stream["height"]),
            fps=fps,
            video_codec=str(video_stream["codec_name"]),
            audio_codec=(
                str(audio_stream["codec_name"]) if audio_stream is not None else "None"
            ),
            bitrate_bps=int(bitrate),
        )
    except (
        KeyError,
        StopIteration,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise MediaProbeError(
            "ffprobe returned incomplete or invalid video metadata."
        ) from error


def probe_video(path: Path) -> VideoMetadata:
    """Run ffprobe for a local video and return its metadata."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        (
            "format=duration,bit_rate:"
            "stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,"
            "bit_rate"
        ),
        "-of",
        "json",
        str(path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as error:
        raise MediaProbeError(
            "FFmpeg is not installed or ffprobe is not available on PATH. "
            "Install FFmpeg from https://ffmpeg.org/download.html, ensure "
            "ffprobe.exe is on PATH, and restart Spotlight."
        ) from error
    except subprocess.TimeoutExpired as error:
        raise MediaProbeError(
            "ffprobe took too long to inspect the selected file."
        ) from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or "The selected file could not be inspected."
        raise MediaProbeError(f"ffprobe failed: {detail}") from error

    return parse_ffprobe_output(result.stdout)
