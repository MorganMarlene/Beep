"""Project-independent local playback and source-time coordination."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget

SOURCE_MICROSECONDS_PER_SECOND = 1_000_000
SOURCE_MICROSECONDS_PER_MILLISECOND = 1_000
TIMELINE_MAXIMUM = 1_000_000
POSITION_UPDATE_INTERVAL_MS = 33


class TimedRange(Protocol):
    """Structural type for transcript segments and clip candidates."""

    @property
    def start_seconds(self) -> float: ...

    @property
    def end_seconds(self) -> float: ...


@dataclass(frozen=True, slots=True)
class LocalMediaSource:
    """A neutral local source value resolved outside the playback module."""

    source_id: int
    path: Path
    duration_us: int


@dataclass(frozen=True, slots=True)
class PlaybackClockSnapshot:
    """Immutable presentation state published by the central playback clock."""

    source_id: int | None = None
    duration_us: int = 0
    requested_position_us: int = 0
    effective_position_us: int = 0
    state: str = "empty"
    seeking: bool = False
    available: bool = False
    error: str | None = None

    @property
    def display_position_us(self) -> int:
        """Return the requested seek position until the backend catches up."""
        if self.seeking:
            return self.requested_position_us
        return self.effective_position_us


class PlaybackSignals(QObject):
    """Backend events tagged with the neutral source identity."""

    source_loaded = Signal(int, int)
    position_changed = Signal(int, int)
    state_changed = Signal(int, str)
    seeking_changed = Signal(int, bool)
    failed = Signal(int, str)


class PlaybackPort(Protocol):
    """Replaceable transport boundary consumed by the playback clock."""

    signals: PlaybackSignals

    @property
    def diagnostics(self) -> str:
        """Describe the observable playback backend without guessing hardware use."""
        ...

    def load(self, source: LocalMediaSource) -> None:
        """Begin loading a local source asynchronously."""

    def clear(self) -> None:
        """Release the current source."""

    def play(self) -> None:
        """Begin playback."""

    def pause(self) -> None:
        """Pause playback."""

    def seek(self, position_us: int) -> None:
        """Request a source-relative time asynchronously."""

    def close(self) -> None:
        """Release playback resources."""


class QtPlaybackAdapter(QObject):
    """Qt Multimedia implementation of the project-neutral playback port."""

    def __init__(self, video_output: QVideoWidget) -> None:
        super().__init__()
        self.signals = PlaybackSignals()
        self._audio_output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.setVideoOutput(video_output)
        self._source: LocalMediaSource | None = None
        self._expected_url = QUrl()
        self._events_enabled = False
        self._loaded_emitted = False

        self._player.sourceChanged.connect(self._on_source_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

    @property
    def diagnostics(self) -> str:
        """Report only backend facts Qt exposes consistently."""
        return (
            "Qt Multimedia; video hardware acceleration is selected by the "
            "platform backend and driver and is not confirmed by BEEP."
        )

    def load(self, source: LocalMediaSource) -> None:
        """Load a source through Qt without reading media into Python memory."""
        self._events_enabled = False
        self._loaded_emitted = False
        self._player.stop()
        self._player.setSource(QUrl())
        self._source = source
        self._expected_url = QUrl.fromLocalFile(str(source.path))
        self._player.setSource(self._expected_url)
        if self._player.source() == self._expected_url:
            self._events_enabled = True

    def clear(self) -> None:
        """Stop playback and release the current media reference."""
        self._events_enabled = False
        self._loaded_emitted = False
        self._player.stop()
        self._player.setSource(QUrl())
        self._source = None
        self._expected_url = QUrl()

    def play(self) -> None:
        """Ask Qt to start playback."""
        if self._source is not None and self._events_enabled:
            self._player.play()

    def pause(self) -> None:
        """Ask Qt to pause playback."""
        if self._source is not None:
            self._player.pause()

    def seek(self, position_us: int) -> None:
        """Translate source microseconds to Qt milliseconds and seek."""
        source = self._source
        if source is None or not self._events_enabled:
            return
        target_ms = source_us_to_qt_ms(
            clamp_position_us(position_us, source.duration_us)
        )
        if abs(self._player.position() - target_ms) <= 1:
            self.signals.position_changed.emit(
                source.source_id, qt_ms_to_source_us(self._player.position())
            )
            self.signals.seeking_changed.emit(source.source_id, False)
            return
        self.signals.seeking_changed.emit(source.source_id, True)
        self._player.setPosition(target_ms)

    def close(self) -> None:
        """Release the source and detach native outputs."""
        self.clear()

    @Slot(QUrl)
    def _on_source_changed(self, source_url: QUrl) -> None:
        self._events_enabled = (
            self._source is not None
            and not source_url.isEmpty()
            and source_url == self._expected_url
        )

    @Slot(int)
    def _on_duration_changed(self, duration_ms: int) -> None:
        source = self._active_source()
        if source is None or duration_ms <= 0:
            return
        self._emit_loaded(source, qt_ms_to_source_us(duration_ms))

    @Slot(object)
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        source = self._active_source()
        if source is None:
            return
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            duration_us = qt_ms_to_source_us(self._player.duration())
            self._emit_loaded(source, duration_us or source.duration_us)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._emit_error(source, self._player.errorString())

    @Slot(int)
    def _on_position_changed(self, position_ms: int) -> None:
        source = self._active_source()
        if source is None:
            return
        self.signals.position_changed.emit(
            source.source_id, qt_ms_to_source_us(position_ms)
        )
        self.signals.seeking_changed.emit(source.source_id, False)

    @Slot(object)
    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        source = self._active_source()
        if source is None:
            return
        state_name = {
            QMediaPlayer.PlaybackState.PlayingState: "playing",
            QMediaPlayer.PlaybackState.PausedState: "paused",
            QMediaPlayer.PlaybackState.StoppedState: "stopped",
        }.get(state, "stopped")
        self.signals.state_changed.emit(source.source_id, state_name)

    @Slot(object, str)
    def _on_error(self, _error: QMediaPlayer.Error, error_text: str) -> None:
        source = self._active_source()
        if source is not None:
            self._emit_error(source, error_text)

    def _active_source(self) -> LocalMediaSource | None:
        if not self._events_enabled:
            return None
        return self._source

    def _emit_loaded(self, source: LocalMediaSource, duration_us: int) -> None:
        if self._loaded_emitted:
            return
        self._loaded_emitted = True
        self.signals.source_loaded.emit(source.source_id, duration_us)

    def _emit_error(self, source: LocalMediaSource, error_text: str) -> None:
        self.signals.seeking_changed.emit(source.source_id, False)
        detail = error_text.strip() or "The Qt multimedia backend rejected this file."
        self.signals.failed.emit(source.source_id, detail)


class PlaybackClock(QObject):
    """Central one-to-many playback state coordinator."""

    snapshot_changed = Signal(object)

    def __init__(self, adapter: PlaybackPort) -> None:
        super().__init__()
        self.adapter = adapter
        self.snapshot = PlaybackClockSnapshot()
        self._pending_position_us: int | None = None
        self._position_timer = QTimer(self)
        self._position_timer.setSingleShot(True)
        self._position_timer.setInterval(POSITION_UPDATE_INTERVAL_MS)
        self._position_timer.timeout.connect(self.flush_pending_position)

        adapter.signals.source_loaded.connect(self._source_loaded)
        adapter.signals.position_changed.connect(self._position_changed)
        adapter.signals.state_changed.connect(self._state_changed)
        adapter.signals.seeking_changed.connect(self._seeking_changed)
        adapter.signals.failed.connect(self._failed)

    def load(self, source: LocalMediaSource) -> None:
        """Reset transient state and ask the adapter to load a local source."""
        self._pending_position_us = None
        self._position_timer.stop()
        self.snapshot = PlaybackClockSnapshot(
            source_id=source.source_id,
            duration_us=max(0, source.duration_us),
            state="loading",
        )
        self._publish()
        self.adapter.load(source)

    def clear(self) -> None:
        """Release the active source and reset the clock."""
        self._pending_position_us = None
        self._position_timer.stop()
        self.adapter.clear()
        self.snapshot = PlaybackClockSnapshot()
        self._publish()

    def toggle_play_pause(self) -> None:
        """Toggle transport state when playback is available."""
        if not self.snapshot.available:
            return
        if self.snapshot.state == "playing":
            self.adapter.pause()
        else:
            self.adapter.play()

    def seek(self, position_us: int) -> None:
        """Publish seek intent immediately, then delegate asynchronously."""
        if not self.snapshot.available or self.snapshot.source_id is None:
            return
        target_us = clamp_position_us(position_us, self.snapshot.duration_us)
        if target_us == self.snapshot.effective_position_us:
            self.snapshot = replace(
                self.snapshot,
                requested_position_us=target_us,
                seeking=False,
            )
            self._publish()
            return
        self.snapshot = replace(
            self.snapshot,
            requested_position_us=target_us,
            seeking=True,
            error=None,
        )
        self._publish()
        self.adapter.seek(target_us)

    def close(self) -> None:
        """Stop timers and release the adapter."""
        self._position_timer.stop()
        self.adapter.close()
        self.snapshot = PlaybackClockSnapshot()

    @Slot(int, int)
    def _source_loaded(self, source_id: int, duration_us: int) -> None:
        if source_id != self.snapshot.source_id:
            return
        self.snapshot = replace(
            self.snapshot,
            duration_us=max(0, duration_us),
            state="paused",
            available=True,
            error=None,
        )
        self._publish()

    @Slot(int, int)
    def _position_changed(self, source_id: int, position_us: int) -> None:
        if source_id != self.snapshot.source_id:
            return
        self._pending_position_us = clamp_position_us(
            position_us, self.snapshot.duration_us
        )
        if not self._position_timer.isActive():
            self._position_timer.start()

    @Slot()
    def flush_pending_position(self) -> None:
        """Publish only the latest backend position in the coalescing interval."""
        if self._pending_position_us is None:
            return
        position_us = self._pending_position_us
        self._pending_position_us = None
        self.snapshot = replace(
            self.snapshot,
            effective_position_us=position_us,
            requested_position_us=(
                self.snapshot.requested_position_us
                if self.snapshot.seeking
                else position_us
            ),
        )
        self._publish()

    @Slot(int, str)
    def _state_changed(self, source_id: int, state: str) -> None:
        if source_id != self.snapshot.source_id:
            return
        self.snapshot = replace(self.snapshot, state=state)
        self._publish()

    @Slot(int, bool)
    def _seeking_changed(self, source_id: int, seeking: bool) -> None:
        if source_id != self.snapshot.source_id:
            return
        if not seeking:
            self.flush_pending_position()
        self.snapshot = replace(self.snapshot, seeking=seeking)
        self._publish()

    @Slot(int, str)
    def _failed(self, source_id: int, message: str) -> None:
        if source_id != self.snapshot.source_id:
            return
        self._pending_position_us = None
        self._position_timer.stop()
        self.snapshot = replace(
            self.snapshot,
            state="error",
            seeking=False,
            available=False,
            error=message,
        )
        self._publish()

    def _publish(self) -> None:
        self.snapshot_changed.emit(self.snapshot)


def seconds_to_source_us(seconds: float) -> int:
    """Convert non-negative source seconds to integer microseconds."""
    return max(0, round(seconds * SOURCE_MICROSECONDS_PER_SECOND))


def source_us_to_qt_ms(position_us: int) -> int:
    """Convert source microseconds to Qt milliseconds using nearest rounding."""
    safe_position = max(0, position_us)
    return (safe_position + SOURCE_MICROSECONDS_PER_MILLISECOND // 2) // (
        SOURCE_MICROSECONDS_PER_MILLISECOND
    )


def qt_ms_to_source_us(position_ms: int) -> int:
    """Convert Qt milliseconds to source microseconds."""
    return max(0, position_ms) * SOURCE_MICROSECONDS_PER_MILLISECOND


def clamp_position_us(position_us: int, duration_us: int) -> int:
    """Clamp a source position to the known media interval."""
    if duration_us <= 0:
        return max(0, position_us)
    return min(max(0, position_us), duration_us)


def format_playback_time(position_us: int) -> str:
    """Format source microseconds as HH:MM:SS.mmm."""
    total_ms = source_us_to_qt_ms(position_us)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def timeline_value_from_position(
    position_us: int,
    duration_us: int,
    maximum: int = TIMELINE_MAXIMUM,
) -> int:
    """Map a source position onto a bounded timeline value."""
    if duration_us <= 0 or maximum <= 0:
        return 0
    clamped = clamp_position_us(position_us, duration_us)
    return round((clamped / duration_us) * maximum)


def position_from_timeline_value(
    value: int,
    duration_us: int,
    maximum: int = TIMELINE_MAXIMUM,
) -> int:
    """Map a bounded timeline value back to source microseconds."""
    if duration_us <= 0 or maximum <= 0:
        return 0
    clamped_value = min(max(0, value), maximum)
    return round((clamped_value / maximum) * duration_us)


def find_active_transcript_index(
    ranges: Sequence[TimedRange],
    position_us: int,
    start_times: Sequence[float] | None = None,
) -> int | None:
    """Find a start-inclusive, end-exclusive transcript range by binary search."""
    if not ranges:
        return None
    position_seconds = position_us / SOURCE_MICROSECONDS_PER_SECOND
    ordered_starts = (
        start_times
        if start_times is not None
        else tuple(item.start_seconds for item in ranges)
    )
    candidate_index = bisect_right(ordered_starts, position_seconds) - 1
    if candidate_index < 0:
        return None
    candidate = ranges[candidate_index]
    if candidate.start_seconds <= position_seconds < candidate.end_seconds:
        return candidate_index
    return None


def find_active_candidate_index(
    ranges: Sequence[TimedRange], position_us: int
) -> int | None:
    """Return the first, therefore highest-ranked, matching candidate range."""
    position_seconds = position_us / SOURCE_MICROSECONDS_PER_SECOND
    for index, candidate in enumerate(ranges):
        if candidate.start_seconds <= position_seconds < candidate.end_seconds:
            return index
    return None
