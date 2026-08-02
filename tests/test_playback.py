from pathlib import Path

from PySide6.QtCore import QObject

from spotlight.clip_detection import ClipCandidate
from spotlight.playback import (
    LocalMediaSource,
    PlaybackClock,
    PlaybackSignals,
    clamp_position_us,
    find_active_candidate_index,
    find_active_transcript_index,
    format_playback_time,
    position_from_timeline_value,
    qt_ms_to_source_us,
    seconds_to_source_us,
    source_us_to_qt_ms,
    timeline_value_from_position,
)
from spotlight.transcription import TranscriptSegment


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


def make_candidate(start: float, end: float, score: int) -> ClipCandidate:
    return ClipCandidate(
        start_segment=0,
        end_segment=0,
        start_seconds=start,
        end_seconds=end,
        clip_type="funny dialogue",
        score=score,
        summary="A complete moment.",
        selection_reasoning="It has setup and payoff.",
        strong_signals=("funny dialogue",),
        weaknesses=(),
    )


def test_source_time_conversion_and_formatting() -> None:
    assert seconds_to_source_us(1.234567) == 1_234_567
    assert seconds_to_source_us(-1.0) == 0
    assert source_us_to_qt_ms(1_499) == 1
    assert source_us_to_qt_ms(1_500) == 2
    assert qt_ms_to_source_us(1_234) == 1_234_000
    assert format_playback_time(3_661_234_000) == "01:01:01.234"


def test_seek_clamping_and_timeline_mapping() -> None:
    duration_us = 10_000_000

    assert clamp_position_us(-1, duration_us) == 0
    assert clamp_position_us(11_000_000, duration_us) == duration_us
    assert timeline_value_from_position(2_500_000, duration_us) == 250_000
    assert position_from_timeline_value(250_000, duration_us) == 2_500_000
    assert position_from_timeline_value(2_000_000, duration_us) == duration_us


def test_active_transcript_uses_start_inclusive_end_exclusive_boundaries() -> None:
    segments = (
        TranscriptSegment(0.0, 2.0, "First"),
        TranscriptSegment(3.0, 5.0, "Second"),
    )

    assert find_active_transcript_index(segments, 0) == 0
    assert find_active_transcript_index(segments, 1_999_999) == 0
    assert find_active_transcript_index(segments, 2_000_000) is None
    assert find_active_transcript_index(segments, 3_000_000) == 1
    assert find_active_transcript_index(segments, 5_000_000) is None


def test_active_candidate_prefers_first_ranked_overlap() -> None:
    candidates = (
        make_candidate(2.0, 8.0, 95),
        make_candidate(4.0, 9.0, 80),
    )

    assert find_active_candidate_index(candidates, 5_000_000) == 0
    assert find_active_candidate_index(candidates, 9_000_000) is None


def test_clock_publishes_seek_immediately_to_multiple_subscribers() -> None:
    adapter = FakePlaybackAdapter()
    clock = PlaybackClock(adapter)
    first: list[object] = []
    second: list[object] = []
    clock.snapshot_changed.connect(first.append)
    clock.snapshot_changed.connect(second.append)
    source = LocalMediaSource(7, Path("video.mp4"), 10_000_000)

    clock.load(source)
    adapter.signals.source_loaded.emit(7, 10_000_000)
    clock.seek(12_000_000)

    assert adapter.seeks == [10_000_000]
    assert clock.snapshot.seeking
    assert clock.snapshot.display_position_us == 10_000_000
    assert first[-1] == second[-1] == clock.snapshot


def test_clock_preserves_multi_hour_microseconds_across_qt_signals() -> None:
    adapter = FakePlaybackAdapter()
    clock = PlaybackClock(adapter)
    duration_us = 10_124_359_667
    target_us = 9_000_000_000

    clock.load(LocalMediaSource(8, Path("long-vod.mp4"), duration_us))
    adapter.signals.source_loaded.emit(8, duration_us)
    clock.seek(target_us)

    assert clock.snapshot.available
    assert clock.snapshot.duration_us == duration_us
    assert clock.snapshot.display_position_us == target_us
    assert adapter.seeks == [target_us]


def test_clock_coalesces_positions_and_rejects_stale_sources() -> None:
    adapter = FakePlaybackAdapter()
    clock = PlaybackClock(adapter)
    clock.load(LocalMediaSource(2, Path("current.mov"), 8_000_000))
    adapter.signals.source_loaded.emit(2, 8_000_000)

    adapter.signals.position_changed.emit(1, 7_000_000)
    adapter.signals.position_changed.emit(2, 1_000_000)
    adapter.signals.position_changed.emit(2, 2_000_000)
    clock.flush_pending_position()

    assert clock.snapshot.effective_position_us == 2_000_000
    assert clock.snapshot.source_id == 2


def test_clock_failure_and_close_release_transient_state() -> None:
    adapter = FakePlaybackAdapter()
    clock = PlaybackClock(adapter)
    clock.load(LocalMediaSource(4, Path("broken.mp4"), 5_000_000))

    adapter.signals.failed.emit(4, "Decoder unavailable")

    assert not clock.snapshot.available
    assert clock.snapshot.error == "Decoder unavailable"
    clock.close()
    assert adapter.close_count == 1


def test_source_descriptor_memory_is_independent_of_media_duration() -> None:
    short = LocalMediaSource(1, Path("short.mp4"), 1_000_000)
    long = LocalMediaSource(2, Path("multi-hour.mp4"), 36_000_000_000)

    assert short.__sizeof__() == long.__sizeof__()
    assert all(
        not isinstance(value, bytes) for value in (short.path, short.duration_us)
    )
