"""Spotlight's PySide6 application setup."""

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spotlight.media import MediaProbeError, VideoMetadata, probe_video
from spotlight.theme import DARK_STYLESHEET
from spotlight.transcription import (
    CudaRuntimeUnavailableError,
    TranscriptionError,
    TranscriptionResult,
    TranscriptSegment,
    transcribe_video,
)


class ProbeSignals(QObject):
    """Signals emitted by a background ffprobe task."""

    succeeded = Signal(object)
    failed = Signal(str)


class ProbeTask(QRunnable):
    """Inspect one video away from the UI thread."""

    def __init__(self, video_path: Path) -> None:
        super().__init__()
        self.video_path = video_path
        self.signals = ProbeSignals()

    @Slot()
    def run(self) -> None:
        """Run ffprobe and report its result to the UI."""
        try:
            metadata = probe_video(self.video_path)
        except MediaProbeError as error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.succeeded.emit(metadata)


class TranscriptionSignals(QObject):
    """Signals emitted by a background transcription task."""

    progressed = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str)
    cuda_runtime_failed = Signal(str)


class TranscriptionTask(QRunnable):
    """Extract and transcribe one video away from the UI thread."""

    def __init__(
        self,
        video_path: Path,
        duration_seconds: float,
        force_cpu: bool = False,
    ) -> None:
        super().__init__()
        self.video_path = video_path
        self.duration_seconds = duration_seconds
        self.force_cpu = force_cpu
        self.signals = TranscriptionSignals()

    @Slot()
    def run(self) -> None:
        """Run transcription and report progress to the UI."""
        try:
            result = transcribe_video(
                self.video_path,
                self.duration_seconds,
                self.signals.progressed.emit,
                force_cpu=self.force_cpu,
            )
        except CudaRuntimeUnavailableError as error:
            self.signals.cuda_runtime_failed.emit(str(error))
        except TranscriptionError as error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.succeeded.emit(result)


class SpotlightWindow(QMainWindow):
    """Main application window for selecting a local video."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Spotlight")
        self.setMinimumSize(960, 700)
        self.setStyleSheet(DARK_STYLESHEET)

        self.open_button = QPushButton("Open Video...")
        self.open_button.clicked.connect(self.open_video)

        self.info_panel = QPlainTextEdit()
        self.info_panel.setReadOnly(True)
        self.info_panel.setPlaceholderText("Open a video to view its details.")
        self.info_panel.setMaximumHeight(190)
        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.setObjectName("TranscribeButton")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.use_cpu_button = QPushButton("Use CPU Instead")
        self.use_cpu_button.setObjectName("CpuButton")
        self.use_cpu_button.setVisible(False)
        self.use_cpu_button.clicked.connect(self.start_cpu_transcription)
        self.progress_label = QLabel("Ready")
        self.progress_label.setObjectName("StatusValue")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.transcript_panel = QPlainTextEdit()
        self.transcript_panel.setReadOnly(True)
        self.transcript_panel.setPlaceholderText(
            "Your timestamped transcript will appear here."
        )
        self.device_value = self._create_status_value("—")
        self.model_value = self._create_status_value("—")
        self.time_value = self._create_status_value("—")
        self.cuda_source_value = QLabel("CUDA Libraries: —")
        self.cuda_source_value.setObjectName("MutedText")
        self.cuda_source_value.setWordWrap(True)
        self._file_details = ""
        self._video_path: Path | None = None
        self._video_duration = 0.0
        self.transcript_segments: list[TranscriptSegment] = []

        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_header())

        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        workspace_layout.addWidget(self._build_sidebar())
        workspace_layout.addWidget(self._build_main_content(), 1)
        root_layout.addWidget(workspace, 1)
        root_layout.addWidget(self._build_status_area())

        self.setCentralWidget(root)
        self.resize(1180, 820)

    @staticmethod
    def _create_status_value(text: str) -> QLabel:
        value = QLabel(text)
        value.setObjectName("StatusValue")
        return value

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(78)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 0, 28, 0)

        brand = QLabel("Spot")
        brand.setObjectName("Brand")
        brand_accent = QLabel("light")
        brand_accent.setObjectName("BrandAccent")
        layout.addWidget(brand)
        layout.addWidget(brand_accent)
        layout.addStretch()

        milestone = QLabel("LOCAL TRANSCRIPTION  /  VERSION 0.1")
        milestone.setObjectName("Eyebrow")
        layout.addWidget(milestone)
        return header

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(22, 28, 18, 22)
        layout.setSpacing(14)

        title = QLabel("WORKSPACE")
        title.setObjectName("SidebarTitle")
        layout.addWidget(title)

        active_item = QFrame()
        active_item.setObjectName("ActiveNavigation")
        active_layout = QHBoxLayout(active_item)
        active_layout.setContentsMargins(14, 11, 12, 11)
        active_label = QLabel("Transcription")
        active_label.setObjectName("ActiveNavigationText")
        active_layout.addWidget(active_label)
        layout.addWidget(active_item)
        layout.addStretch()

        local_label = QLabel("●  LOCAL PROCESSING")
        local_label.setObjectName("Eyebrow")
        layout.addWidget(local_label)
        return sidebar

    def _build_main_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(20)

        video_card = QFrame()
        video_card.setObjectName("Card")
        video_layout = QVBoxLayout(video_card)
        video_layout.setContentsMargins(20, 18, 20, 20)
        video_layout.setSpacing(12)
        video_header = QHBoxLayout()
        video_title = QLabel("Video Details")
        video_title.setObjectName("SectionTitle")
        video_header.addWidget(video_title)
        video_header.addStretch()
        video_header.addWidget(self.open_button)
        video_layout.addLayout(video_header)
        video_layout.addWidget(self.info_panel)
        layout.addWidget(video_card)

        transcript_card = QFrame()
        transcript_card.setObjectName("Card")
        transcript_layout = QVBoxLayout(transcript_card)
        transcript_layout.setContentsMargins(20, 18, 20, 20)
        transcript_layout.setSpacing(12)
        transcript_header = QHBoxLayout()
        transcript_title = QLabel("Transcript")
        transcript_title.setObjectName("SectionTitle")
        transcript_header.addWidget(transcript_title)
        transcript_header.addStretch()
        transcript_header.addWidget(self.use_cpu_button)
        transcript_header.addWidget(self.transcribe_button)
        transcript_layout.addLayout(transcript_header)
        transcript_layout.addWidget(self.transcript_panel, 1)
        layout.addWidget(transcript_card, 1)
        return content

    def _build_status_area(self) -> QFrame:
        status = QFrame()
        status.setObjectName("StatusBar")
        layout = QVBoxLayout(status)
        layout.setContentsMargins(24, 12, 24, 14)
        layout.setSpacing(8)

        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress_label, 1)
        progress_row.addWidget(self.progress_bar, 2)
        layout.addLayout(progress_row)

        metrics = QHBoxLayout()
        metrics.setSpacing(28)
        for caption, value in (
            ("DEVICE", self.device_value),
            ("MODEL", self.model_value),
            ("TOTAL TIME", self.time_value),
        ):
            metric = QVBoxLayout()
            metric.setSpacing(2)
            label = QLabel(caption)
            label.setObjectName("StatusCaption")
            metric.addWidget(label)
            metric.addWidget(value)
            metrics.addLayout(metric)
        metrics.addStretch()
        layout.addLayout(metrics)
        layout.addWidget(self.cuda_source_value)
        return status

    def _reset_runtime_diagnostics(self) -> None:
        self.device_value.setText("—")
        self.model_value.setText("—")
        self.time_value.setText("—")
        self.cuda_source_value.setText("CUDA Libraries: —")

    def open_video(self) -> None:
        """Let the user select a video and display its filesystem details."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi)",
        )
        if not file_path:
            return

        video_path = Path(file_path)
        self._video_path = video_path
        self._video_duration = 0.0
        self.transcribe_button.setEnabled(False)
        self.transcript_segments = []
        self.transcript_panel.clear()
        self.progress_label.setText("Ready")
        self.progress_bar.setValue(0)
        self._reset_runtime_diagnostics()
        self.use_cpu_button.setVisible(False)
        file_details = video_path.stat()
        size_mb = file_details.st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(file_details.st_mtime).astimezone()

        self._file_details = "\n".join(
            (
                f"File Name: {video_path.name}",
                f"Full Path: {video_path.resolve()}",
                f"File Size (MB): {size_mb:.2f}",
                f"Last Modified Date: {modified:%Y-%m-%d %H:%M:%S %Z}",
            )
        )
        self.info_panel.setPlainText(
            f"{self._file_details}\n\nReading video metadata..."
        )
        self.open_button.setEnabled(False)

        task = ProbeTask(video_path)
        task.signals.succeeded.connect(self.display_video_metadata)
        task.signals.failed.connect(self.display_probe_error)
        QThreadPool.globalInstance().start(task)

    @Slot(object)
    def display_video_metadata(self, metadata: VideoMetadata) -> None:
        """Display metadata returned by ffprobe."""
        minutes, seconds = divmod(metadata.duration_seconds, 60)
        hours, minutes = divmod(int(minutes), 60)
        duration = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
        bitrate = (
            f"{metadata.bitrate_bps / 1_000_000:.2f} Mbps"
            if metadata.bitrate_bps
            else "Unknown"
        )

        self.info_panel.setPlainText(
            "\n".join(
                (
                    self._file_details,
                    "",
                    f"Duration: {duration}",
                    f"Resolution: {metadata.width} x {metadata.height}",
                    f"FPS: {metadata.fps:.3f}",
                    f"Video Codec: {metadata.video_codec}",
                    f"Audio Codec: {metadata.audio_codec}",
                    f"Bitrate: {bitrate}",
                )
            )
        )
        self.open_button.setEnabled(True)
        self._video_duration = metadata.duration_seconds
        self.transcribe_button.setEnabled(True)

    @Slot(str)
    def display_probe_error(self, message: str) -> None:
        """Display a friendly ffprobe failure message."""
        self.info_panel.setPlainText(f"{self._file_details}\n\nError: {message}")
        self.open_button.setEnabled(True)
        self._video_path = None
        self.transcribe_button.setEnabled(False)

    @Slot()
    def start_transcription(self, force_cpu: bool = False) -> None:
        """Start audio extraction and transcription in the thread pool."""
        if self._video_path is None:
            return

        self.open_button.setEnabled(False)
        self.transcribe_button.setEnabled(False)
        self.transcript_panel.clear()
        self.progress_bar.setValue(0)
        self.progress_label.setText("Preparing transcription...")
        self._reset_runtime_diagnostics()
        self.use_cpu_button.setVisible(False)

        task = TranscriptionTask(
            self._video_path,
            self._video_duration,
            force_cpu=force_cpu,
        )
        task.signals.progressed.connect(self.display_transcription_progress)
        task.signals.succeeded.connect(self.display_transcript)
        task.signals.failed.connect(self.display_transcription_error)
        task.signals.cuda_runtime_failed.connect(self.display_cuda_runtime_error)
        QThreadPool.globalInstance().start(task)

    @Slot()
    def start_cpu_transcription(self) -> None:
        """Retry transcription explicitly on the CPU."""
        self.start_transcription(force_cpu=True)

    @Slot(int, str)
    def display_transcription_progress(self, value: int, message: str) -> None:
        """Update the transcription progress display."""
        self.progress_bar.setValue(value)
        self.progress_label.setText(message)

    @Slot(object)
    def display_transcript(self, result: TranscriptionResult) -> None:
        """Display the completed timestamped transcript."""
        self.transcript_segments = result.segments
        self.transcript_panel.setPlainText(
            "\n".join(
                f"[{format_timestamp(segment.start_seconds)} - "
                f"{format_timestamp(segment.end_seconds)}] {segment.text}"
                for segment in result.segments
            )
        )
        self.progress_bar.setValue(100)
        elapsed_time = format_elapsed_time(result.elapsed_seconds)
        self.progress_label.setText("Transcription complete.")
        self.device_value.setText(result.compute_device.upper())
        self.model_value.setText(result.model_name)
        self.time_value.setText(elapsed_time)
        self.cuda_source_value.setText(f"CUDA Libraries: {result.cuda_library_source}")
        self.open_button.setEnabled(True)
        self.transcribe_button.setEnabled(True)
        self.use_cpu_button.setVisible(False)

    @Slot(str)
    def display_transcription_error(self, message: str) -> None:
        """Display a friendly transcription failure message."""
        self.progress_label.setText(f"Error: {message}")
        self.progress_bar.setValue(0)
        self.open_button.setEnabled(True)
        self.transcribe_button.setEnabled(self._video_path is not None)
        self.use_cpu_button.setVisible(False)

    @Slot(str)
    def display_cuda_runtime_error(self, message: str) -> None:
        """Explain missing CUDA components and offer a CPU retry."""
        self.progress_label.setText(f"CUDA setup error: {message}")
        self.progress_bar.setValue(0)
        self.open_button.setEnabled(True)
        self.transcribe_button.setEnabled(self._video_path is not None)
        self.use_cpu_button.setVisible(self._video_path is not None)
        self.use_cpu_button.setEnabled(self._video_path is not None)


def format_timestamp(seconds: float) -> str:
    """Format seconds as a transcript timestamp."""
    whole_minutes, remaining_seconds = divmod(seconds, 60)
    hours, minutes = divmod(int(whole_minutes), 60)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:06.3f}"


def format_elapsed_time(seconds: float) -> str:
    """Format an elapsed duration for the transcription summary."""
    minutes, remaining_seconds = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:05.2f}"


def create_window() -> SpotlightWindow:
    """Create the main Spotlight window."""
    return SpotlightWindow()


def main() -> int:
    """Run Spotlight until the main window is closed."""
    application = QApplication(sys.argv)
    window = create_window()
    window.show()
    return application.exec()
