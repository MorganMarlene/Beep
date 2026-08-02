import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from spotlight.playback import (  # noqa: E402
    LocalMediaSource,
    QtPlaybackAdapter,
    seconds_to_source_us,
)

RUN_INTEGRATION = os.environ.get("BEEP_RUN_PLAYBACK_INTEGRATION") == "1"


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])


def wait_for(
    application: QApplication, predicate: Callable[[], bool], attempts: int = 100
) -> bool:
    for _ in range(attempts):
        application.processEvents()
        if predicate():
            return True
        QTest.qWait(10)
    return False


@pytest.mark.skipif(
    not RUN_INTEGRATION or sys.platform != "win32",
    reason="Set BEEP_RUN_PLAYBACK_INTEGRATION=1 on Windows to test Qt playback.",
)
@pytest.mark.parametrize("suffix", [".mp4", ".mov"])
def test_qt_backend_loads_generated_h264_aac_source(
    application: QApplication, tmp_path: Path, suffix: str
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg is required to generate the temporary fixture.")
    media_path = tmp_path / f"fixture{suffix}"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-y",
            str(media_path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    video_output = QVideoWidget()
    adapter = QtPlaybackAdapter(video_output)
    loaded: list[tuple[int, int]] = []
    failures: list[str] = []
    positions: list[int] = []
    adapter.signals.source_loaded.connect(
        lambda source_id, duration: loaded.append((source_id, duration))
    )
    adapter.signals.failed.connect(lambda _source_id, message: failures.append(message))
    adapter.signals.position_changed.connect(
        lambda _source_id, position: positions.append(position)
    )

    adapter.load(LocalMediaSource(1, media_path, seconds_to_source_us(1.0)))

    assert wait_for(application, lambda: bool(loaded or failures))
    assert not failures
    assert loaded[0][1] > 0
    adapter.seek(500_000)
    assert wait_for(application, lambda: bool(positions))
    adapter.close()


@pytest.mark.skipif(
    not RUN_INTEGRATION or sys.platform != "win32",
    reason="Set BEEP_RUN_PLAYBACK_INTEGRATION=1 on Windows to measure seeking.",
)
def test_reference_mp4_seek_presentation_is_responsive(
    application: QApplication, tmp_path: Path
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg is required to generate the temporary fixture.")
    media_path = tmp_path / "seek-fixture.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=30:duration=3",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=3",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-y",
            str(media_path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    video_output = QVideoWidget()
    adapter = QtPlaybackAdapter(video_output)
    loaded: list[tuple[int, int]] = []
    positions: list[int] = []
    frames: list[int] = []
    adapter.signals.source_loaded.connect(
        lambda source_id, duration: loaded.append((source_id, duration))
    )
    adapter.signals.position_changed.connect(
        lambda _source_id, position: positions.append(position)
    )
    video_output.videoSink().videoFrameChanged.connect(
        lambda frame: frames.append(frame.startTime()) if frame.isValid() else None
    )
    adapter.load(LocalMediaSource(1, media_path, seconds_to_source_us(3.0)))
    assert wait_for(application, lambda: bool(loaded))
    adapter.play()
    assert wait_for(application, lambda: bool(frames))
    adapter.pause()

    latencies_ms: list[float] = []
    for target_us in (250_000, 750_000, 1_250_000, 1_750_000, 2_250_000):
        position_count = len(positions)
        frame_count = len(frames)
        started = time.perf_counter()
        adapter.seek(target_us)
        assert wait_for(
            application,
            lambda: len(positions) > position_count and len(frames) > frame_count,
        )
        latencies_ms.append((time.perf_counter() - started) * 1_000)

    p95_ms = sorted(latencies_ms)[-1]
    print(f"Qt decoded-frame seek p95: {p95_ms:.1f} ms")
    assert p95_ms <= 250
    adapter.close()
