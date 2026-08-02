import os
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from spotlight.app import SpotlightWindow  # noqa: E402
from spotlight.clip_detection import ClipCandidate  # noqa: E402
from spotlight.media import VideoMetadata  # noqa: E402
from spotlight.playback import LocalMediaSource, PlaybackSignals  # noqa: E402
from spotlight.transcription import TranscriptSegment  # noqa: E402


class FakePlaybackAdapter(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.signals = PlaybackSignals()
        self.loaded_sources: list[LocalMediaSource] = []
        self.seeks: list[int] = []
        self.play_count = 0
        self.pause_count = 0
        self.clear_count = 0
        self.close_count = 0

    @property
    def diagnostics(self) -> str:
        return "Fake playback adapter"

    def load(self, source: LocalMediaSource) -> None:
        self.loaded_sources.append(source)

    def clear(self) -> None:
        self.clear_count += 1

    def play(self) -> None:
        self.play_count += 1

    def pause(self) -> None:
        self.pause_count += 1

    def seek(self, position_us: int) -> None:
        self.seeks.append(position_us)

    def close(self) -> None:
        self.close_count += 1


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])


def make_metadata(duration: float = 30.0) -> VideoMetadata:
    return VideoMetadata(duration, 1920, 1080, 30.0, "h264", "aac", 4_000_000)


def make_candidate() -> ClipCandidate:
    return ClipCandidate(
        start_segment=1,
        end_segment=1,
        start_seconds=10.0,
        end_seconds=20.0,
        clip_type="deadpan humor",
        score=95,
        summary="A complete joke.",
        selection_reasoning="Setup and payoff.",
        strong_signals=("deadpan humor",),
        weaknesses=("Visual context unavailable.",),
    )


def load_fake_source(
    window: SpotlightWindow,
    adapter: FakePlaybackAdapter,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "review.mp4"
    source_path.touch()
    window._load_playback_source(source_path, make_metadata())
    source = adapter.loaded_sources[-1]
    adapter.signals.source_loaded.emit(source.source_id, source.duration_us)


def test_transcript_and_candidate_activation_seek_exact_starts(
    application: QApplication, tmp_path: Path
) -> None:
    adapter = FakePlaybackAdapter()
    window = SpotlightWindow(playback_adapter=adapter)
    load_fake_source(window, adapter, tmp_path)
    window._show_transcript(
        (
            TranscriptSegment(0.0, 5.0, "First"),
            TranscriptSegment(10.0, 15.0, "Second"),
        )
    )
    window._show_clip_candidates((make_candidate(),))

    window.seek_to_transcript_segment(1)
    window.seek_to_candidate(window.candidate_list.item(0))

    assert adapter.seeks == [10_000_000, 10_000_000]
    window.close()


def test_player_position_synchronizes_views_without_recursive_seek(
    application: QApplication, tmp_path: Path
) -> None:
    adapter = FakePlaybackAdapter()
    window = SpotlightWindow(playback_adapter=adapter)
    load_fake_source(window, adapter, tmp_path)
    window._show_transcript(
        (
            TranscriptSegment(0.0, 5.0, "First searchable line"),
            TranscriptSegment(10.0, 15.0, "Second searchable line"),
        )
    )
    window._show_clip_candidates((make_candidate(),))
    window.search_box.setText("searchable")
    seek_count = len(adapter.seeks)
    source_id = adapter.loaded_sources[-1].source_id

    adapter.signals.position_changed.emit(source_id, 12_000_000)
    window.playback_clock.flush_pending_position()

    assert len(adapter.seeks) == seek_count
    assert window._active_transcript_index == 1
    assert window._active_candidate_index == 0
    assert window.candidate_list.item(0).text().startswith("▶ ")
    assert len(window.transcript_panel.extraSelections()) >= 3
    window.close()


def test_seek_intent_is_reflected_within_ui_target(
    application: QApplication, tmp_path: Path
) -> None:
    adapter = FakePlaybackAdapter()
    window = SpotlightWindow(playback_adapter=adapter)
    load_fake_source(window, adapter, tmp_path)
    latencies_ms: list[float] = []

    for target_us in range(1_000_000, 21_000_000, 1_000_000):
        started = time.perf_counter()
        window.video_workspace.seek_requested.emit(target_us)
        assert window.playback_clock.snapshot.display_position_us == target_us
        latencies_ms.append((time.perf_counter() - started) * 1_000)

    p95_ms = sorted(latencies_ms)[-1]
    assert p95_ms < 100
    window.close()


def test_play_button_reaches_the_playback_adapter(
    application: QApplication, tmp_path: Path
) -> None:
    adapter = FakePlaybackAdapter()
    window = SpotlightWindow(playback_adapter=adapter)
    load_fake_source(window, adapter, tmp_path)

    window.video_workspace.play_pause_button.click()

    assert adapter.play_count == 1
    window.close()


def test_unavailable_and_unsupported_sources_preserve_review_data(
    application: QApplication, tmp_path: Path
) -> None:
    adapter = FakePlaybackAdapter()
    window = SpotlightWindow(playback_adapter=adapter)
    window._show_transcript((TranscriptSegment(0.0, 2.0, "Keep me"),))
    unsupported = tmp_path / "review.mkv"
    unsupported.touch()

    window._load_playback_source(unsupported, make_metadata())
    window.seek_to_transcript_segment(0)

    assert adapter.loaded_sources == []
    assert window.transcript_segments[0].text == "Keep me"
    assert "supports MP4 and MOV" in window.video_workspace.playback_message.text()
    window.close()


def test_project_switch_and_close_release_playback(
    application: QApplication, tmp_path: Path
) -> None:
    adapter = FakePlaybackAdapter()
    window = SpotlightWindow(playback_adapter=adapter)
    load_fake_source(window, adapter, tmp_path)

    window._clear_workspace()

    assert adapter.clear_count >= 2
    assert window.playback_clock.snapshot.source_id is None
    window.close()
    assert adapter.close_count == 1


def test_workspace_is_video_first_and_accessible_at_target_sizes(
    application: QApplication,
) -> None:
    adapter = FakePlaybackAdapter()
    window = SpotlightWindow(playback_adapter=adapter)
    window.show()

    for width, height in ((1920, 1080), (2560, 1440), (3840, 2160)):
        window.resize(width, height)
        application.processEvents()
        sizes = window.video_workspace.primary_splitter.sizes()
        assert sizes[0] > sizes[1]
        assert window.video_workspace.play_pause_button.isVisible()
        assert window.video_workspace.timeline.isVisible()
        assert window.transcript_panel.isVisible()
        assert window.candidate_list.isVisible()

    assert window.video_workspace.play_pause_button.accessibleName()
    assert window.video_workspace.timeline.accessibleName()
    assert window.transcript_panel.accessibleName()
    assert window.video_workspace.timeline.focusPolicy() != Qt.FocusPolicy.NoFocus
    window.close()
