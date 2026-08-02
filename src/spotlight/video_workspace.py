"""Bounded PySide6 video-review workspace for BEEP."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from spotlight.playback import (
    TIMELINE_MAXIMUM,
    PlaybackClockSnapshot,
    format_playback_time,
    position_from_timeline_value,
    timeline_value_from_position,
)
from spotlight.theme import PLAYER_PANE_PERCENT, SPACE_1, SPACE_2, SPACE_3


class TimelineSlider(QSlider):
    """A source-time timeline with one reusable value mapping."""

    source_position_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__(Qt.Orientation.Horizontal)
        self.setObjectName("PlaybackTimeline")
        self.setRange(0, TIMELINE_MAXIMUM)
        self.setTracking(True)
        self.setEnabled(False)
        self.setAccessibleName("Video timeline")
        self.setAccessibleDescription("Seek through the active project's local video.")
        self._duration_us = 0
        self._reflecting_position = False
        self.valueChanged.connect(self._request_position)

    @property
    def duration_us(self) -> int:
        return self._duration_us

    def set_duration_us(self, duration_us: int) -> None:
        self._duration_us = max(0, duration_us)
        self.setEnabled(self._duration_us > 0)
        self.setAccessibleDescription(
            "Seek through the active project's local video. "
            f"Duration {format_playback_time(self._duration_us)}."
        )

    def set_position_us(self, position_us: int) -> None:
        self._reflecting_position = True
        try:
            self.setValue(timeline_value_from_position(position_us, self._duration_us))
            self.setAccessibleDescription(
                "Seek through the active project's local video. "
                f"Current time {format_playback_time(position_us)} of "
                f"{format_playback_time(self._duration_us)}."
            )
        finally:
            self._reflecting_position = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Allow direct groove clicks as well as dragging and keyboard seeking."""
        if event.button() == Qt.MouseButton.LeftButton and self.width() > 0:
            value = QStyle.sliderValueFromPosition(
                self.minimum(),
                self.maximum(),
                round(event.position().x()),
                self.width(),
            )
            self.setValue(value)
            event.accept()
            return
        super().mousePressEvent(event)

    def _request_position(self, value: int) -> None:
        if self._reflecting_position or self._duration_us <= 0:
            return
        self.source_position_requested.emit(
            position_from_timeline_value(value, self._duration_us)
        )


class TranscriptView(QPlainTextEdit):
    """Read-only transcript view with timestamp activation."""

    timestamp_activated = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TranscriptView")
        self.setReadOnly(True)
        self.setAccessibleName("Timestamped transcript")
        self.setAccessibleDescription(
            "Review transcript segments. Activate a timestamp to seek the video."
        )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        cursor = self.cursorForPosition(event.position().toPoint())
        block = cursor.block()
        closing_bracket = block.text().find("]")
        if (
            event.button() == Qt.MouseButton.LeftButton
            and block.isValid()
            and closing_bracket >= 0
            and cursor.positionInBlock() <= closing_bracket
        ):
            self.timestamp_activated.emit(block.blockNumber())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            block = self.textCursor().block()
            if block.isValid():
                self.timestamp_activated.emit(block.blockNumber())
                event.accept()
                return
        super().keyPressEvent(event)


class VideoWorkspace(QWidget):
    """Video-first layout that contains existing review panels unchanged."""

    play_pause_requested = Signal()
    seek_requested = Signal(object)

    def __init__(
        self,
        video_details: QWidget,
        transcript_panel: QWidget,
        candidate_panel: QWidget,
    ) -> None:
        super().__init__()
        self.setObjectName("VideoWorkspace")
        self.video_output = QVideoWidget()
        self.video_output.setObjectName("VideoOutput")
        self.video_output.setMinimumSize(384, 216)
        self.video_output.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video_output.setAccessibleName("Active project video")
        self.video_output.setAccessibleDescription(
            "Local video preview for the active project."
        )

        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.setObjectName("PlaybackButton")
        self.play_pause_button.setEnabled(False)
        self.play_pause_button.setAccessibleName("Play video")
        self.play_pause_button.clicked.connect(self.play_pause_requested)

        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        self.time_label.setObjectName("PlaybackTime")
        self.time_label.setAccessibleName("Current playback time")

        self.seeking_label = QLabel("Seeking...")
        self.seeking_label.setObjectName("SeekingStatus")
        self.seeking_label.setAccessibleName("Playback status")
        self.seeking_label.setVisible(False)

        self.timeline = TimelineSlider()
        self.timeline.source_position_requested.connect(self.seek_requested)

        self.playback_message = QLabel(
            "Open an MP4 or MOV in the active project to enable playback."
        )
        self.playback_message.setObjectName("PlaybackMessage")
        self.playback_message.setWordWrap(True)
        self.playback_message.setAccessibleName("Playback information")

        self.player_card = self._build_player_card()
        self.left_pane = QWidget()
        self.left_layout = QVBoxLayout(self.left_pane)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(SPACE_2)
        self.left_layout.addWidget(self.player_card, 6)
        self.left_layout.addWidget(video_details, 1)
        self.video_details = video_details

        self.review_splitter = QSplitter(Qt.Orientation.Vertical)
        self.review_splitter.setObjectName("ReviewSplitter")
        self.review_splitter.setChildrenCollapsible(False)
        self.review_splitter.addWidget(transcript_panel)
        self.review_splitter.addWidget(candidate_panel)
        self.review_splitter.setStretchFactor(0, 3)
        self.review_splitter.setStretchFactor(1, 2)
        self.review_splitter.setSizes([560, 360])

        self.primary_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.primary_splitter.setObjectName("WorkspaceSplitter")
        self.primary_splitter.setChildrenCollapsible(False)
        self.primary_splitter.addWidget(self.left_pane)
        self.primary_splitter.addWidget(self.review_splitter)
        self.primary_splitter.setStretchFactor(0, 13)
        self.primary_splitter.setStretchFactor(1, 7)
        self.primary_splitter.setSizes([1280, 720])

        self.workspace_layout = QVBoxLayout(self)
        self.workspace_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        self.workspace_layout.addWidget(self.primary_splitter)

    def _build_player_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("PlayerCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACE_2, SPACE_2, SPACE_2, SPACE_2)
        layout.setSpacing(SPACE_1)

        title = QLabel("Video Review")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        layout.addWidget(self.video_output, 1)
        layout.addWidget(self.playback_message)
        layout.addWidget(self.timeline)

        controls = QHBoxLayout()
        controls.setSpacing(SPACE_2)
        controls.addWidget(self.play_pause_button)
        controls.addWidget(self.time_label)
        controls.addStretch()
        controls.addWidget(self.seeking_label)
        layout.addLayout(controls)
        return card

    def apply_density(self, *, expanded: bool, workspace_width: int) -> None:
        """Adapt presentation geometry without rebuilding stateful widgets."""
        margin = SPACE_3 if expanded else SPACE_2
        self.workspace_layout.setContentsMargins(margin, SPACE_2, margin, SPACE_2)
        self.left_layout.setSpacing(SPACE_2 if expanded else SPACE_1)
        self.video_details.setMaximumHeight(160 if expanded else 136)
        if expanded:
            self.video_output.setMinimumSize(480, 272)
        else:
            self.video_output.setMinimumSize(384, 216)

        usable_width = max(800, workspace_width - (margin * 2))
        player_width = round(usable_width * PLAYER_PANE_PERCENT / 100)
        self.primary_splitter.setSizes([player_width, usable_width - player_width])

    def set_clock_snapshot(self, snapshot: PlaybackClockSnapshot) -> None:
        """Reflect clock state without emitting another seek."""
        position_us = snapshot.display_position_us
        self.timeline.set_duration_us(snapshot.duration_us)
        self.timeline.set_position_us(position_us)
        self.timeline.setEnabled(snapshot.available and snapshot.duration_us > 0)
        self.play_pause_button.setEnabled(snapshot.available)
        is_playing = snapshot.state == "playing"
        self.play_pause_button.setText("Pause" if is_playing else "Play")
        self.play_pause_button.setAccessibleName(
            "Pause video" if is_playing else "Play video"
        )
        self.time_label.setText(
            f"{format_playback_time(position_us)} / "
            f"{format_playback_time(snapshot.duration_us)}"
        )
        self.time_label.setAccessibleDescription(self.time_label.text())
        self.seeking_label.setVisible(snapshot.seeking)
        self.seeking_label.setText("Seeking..." if snapshot.seeking else "Ready")

        if snapshot.error:
            self.set_playback_message(f"Playback unavailable: {snapshot.error}")
        elif snapshot.state == "loading":
            self.set_playback_message("Loading local video...")
        elif snapshot.available:
            self.set_playback_message("Local playback ready.")

    def set_playback_message(self, message: str) -> None:
        """Show a visible and accessible playback status."""
        self.playback_message.setText(message)
        self.playback_message.setAccessibleDescription(message)

    def reset_playback(self, message: str) -> None:
        """Reset controls while preserving the surrounding review panels."""
        self.set_clock_snapshot(PlaybackClockSnapshot())
        self.set_playback_message(message)
