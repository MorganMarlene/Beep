"""BEEP's PySide6 application setup."""

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QCloseEvent, QColor, QFont, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from spotlight.clip_detection import (
    ClipAnalysisError,
    ClipAnalysisResult,
    ClipCandidate,
    analyze_transcript,
)
from spotlight.media import MediaProbeError, VideoMetadata, probe_video
from spotlight.playback import (
    LocalMediaSource,
    PlaybackClock,
    PlaybackClockSnapshot,
    PlaybackPort,
    QtPlaybackAdapter,
    find_active_candidate_index,
    find_active_transcript_index,
    seconds_to_source_us,
)
from spotlight.projects import (
    ProjectRepository,
    ProjectSnapshot,
    ProjectStorageError,
    ProjectSummary,
    StoredVideo,
    default_database_path,
)
from spotlight.theme import DARK_STYLESHEET
from spotlight.transcription import (
    CudaRuntimeUnavailableError,
    TranscriptionError,
    TranscriptionResult,
    TranscriptSegment,
    transcribe_video,
)
from spotlight.video_workspace import TranscriptView, VideoWorkspace

APPLICATION_NAME = "BEEP"
CANDIDATE_BASE_TEXT_ROLE = int(Qt.ItemDataRole.UserRole) + 1


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


class ClipAnalysisSignals(QObject):
    """Signals emitted by a background local clip-analysis task."""

    progressed = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str)


class ClipAnalysisTask(QRunnable):
    """Analyze an immutable transcript away from the UI thread."""

    def __init__(self, segments: tuple[TranscriptSegment, ...]) -> None:
        super().__init__()
        self.segments = segments
        self.signals = ClipAnalysisSignals()

    @Slot()
    def run(self) -> None:
        """Run local Ollama analysis and report its result to the UI."""
        try:
            result = analyze_transcript(self.segments, self.signals.progressed.emit)
        except ClipAnalysisError as error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.succeeded.emit(result)


class NewProjectDialog(QDialog):
    """Collect the small amount of metadata required for a new project."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("Required")
        self.brand_name = QLineEdit()
        self.brand_name.setPlaceholderText("Optional project metadata")
        self.validation_label = QLabel("")
        self.validation_label.setObjectName("ErrorText")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Project name", self.project_name)
        form.addRow("Brand name", self.brand_name)
        layout.addLayout(form)
        layout.addWidget(self.validation_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        """Require a visible non-empty project name before accepting."""
        if not self.project_name.text().strip():
            self.validation_label.setText("Project name is required.")
            self.project_name.setFocus()
            return
        super().accept()


class OpenProjectDialog(QDialog):
    """Select one locally stored project without exposing database files."""

    def __init__(
        self, projects: tuple[ProjectSummary, ...], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open Project")
        self.project_list = QListWidget()
        for project in projects:
            details = project.brand_name or project.filename or "No VOD selected"
            item = self._project_item(project, details)
            self.project_list.addItem(item)
        if self.project_list.count():
            self.project_list.setCurrentRow(0)

        layout = QVBoxLayout(self)
        layout.addWidget(self.project_list)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _project_item(project: ProjectSummary, details: str) -> QListWidgetItem:
        item = QListWidgetItem(f"{project.name}\n{details}")
        item.setData(Qt.ItemDataRole.UserRole, project.project_id)
        return item

    @property
    def selected_project_id(self) -> str | None:
        """Return the stable identity of the current selection."""
        item = self.project_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None


class SpotlightWindow(QMainWindow):
    """Main application window for one active local project."""

    def __init__(
        self,
        repository: ProjectRepository | None = None,
        playback_adapter: PlaybackPort | None = None,
    ) -> None:
        super().__init__()
        self.repository = repository
        self.active_project: ProjectSummary | None = None
        self.setWindowTitle(APPLICATION_NAME)
        self.setMinimumSize(960, 700)
        self.setStyleSheet(DARK_STYLESHEET)

        self.open_button = QPushButton("Open Video...")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_video)

        self.new_project_button = QPushButton("New Project")
        self.new_project_button.setObjectName("SidebarAction")
        self.new_project_button.clicked.connect(self.show_new_project_dialog)
        self.open_project_button = QPushButton("Open Project")
        self.open_project_button.setObjectName("SidebarAction")
        self.open_project_button.clicked.connect(self.show_open_project_dialog)
        self.active_project_value = QLabel("No active project")
        self.active_project_value.setObjectName("ActiveProject")
        self.active_project_value.setWordWrap(True)
        self.recent_projects_list = QListWidget()
        self.recent_projects_list.setObjectName("RecentProjects")
        self.recent_projects_list.itemActivated.connect(self.open_recent_project)

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
        self.transcript_panel = TranscriptView()
        self.transcript_panel.setPlaceholderText(
            "Your timestamped transcript will appear here."
        )
        self.transcript_panel.timestamp_activated.connect(
            self.seek_to_transcript_segment
        )
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search transcript...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self.update_transcript_search)
        self.match_count_label = QLabel("0 matches")
        self.match_count_label.setObjectName("MutedText")
        self.previous_match_button = QPushButton("Previous Match")
        self.previous_match_button.setObjectName("SearchNavigationButton")
        self.previous_match_button.setEnabled(False)
        self.previous_match_button.clicked.connect(self.select_previous_match)
        self.next_match_button = QPushButton("Next Match")
        self.next_match_button.setObjectName("SearchNavigationButton")
        self.next_match_button.setEnabled(False)
        self.next_match_button.clicked.connect(self.select_next_match)
        self.analyze_clips_button = QPushButton("Analyze Clips")
        self.analyze_clips_button.setObjectName("AnalyzeButton")
        self.analyze_clips_button.setEnabled(False)
        self.analyze_clips_button.clicked.connect(self.start_clip_analysis)
        self.candidate_list = QListWidget()
        self.candidate_list.setObjectName("CandidateList")
        self.candidate_list.setMinimumWidth(340)
        self.candidate_list.currentRowChanged.connect(self.display_candidate_details)
        self.candidate_list.itemClicked.connect(self.seek_to_candidate)
        self.candidate_list.itemActivated.connect(self.seek_to_candidate)
        self.candidate_details = QPlainTextEdit()
        self.candidate_details.setReadOnly(True)
        self.candidate_details.setPlaceholderText(
            "Select a ranked candidate to review its signals and weaknesses."
        )
        self.device_value = self._create_status_value("—")
        self.model_value = self._create_status_value("—")
        self.time_value = self._create_status_value("—")
        self.cuda_source_value = QLabel("CUDA Libraries: —")
        self.cuda_source_value.setObjectName("MutedText")
        self.cuda_source_value.setWordWrap(True)
        self.playback_backend_value = QLabel("Playback: not loaded")
        self.playback_backend_value.setObjectName("MutedText")
        self.playback_backend_value.setWordWrap(True)
        self._file_details = ""
        self._video_path: Path | None = None
        self._video_metadata: VideoMetadata | None = None
        self._video_duration = 0.0
        self._file_size_bytes = 0
        self._last_modified_at = ""
        self._pending_video_path: Path | None = None
        self._pending_file_size_bytes = 0
        self._pending_last_modified_at = ""
        self._pending_file_details = ""
        self._previous_info_text = ""
        self._has_saved_projects = False
        self.transcript_segments: list[TranscriptSegment] = []
        self._transcript_start_seconds: tuple[float, ...] = ()
        self.clip_candidates: list[ClipCandidate] = []
        self._match_indices: list[int] = []
        self._search_selections: list[QTextEdit.ExtraSelection] = []
        self._current_match_index: int | None = None
        self._active_transcript_index: int | None = None
        self._active_candidate_index: int | None = None
        self._source_generation = 0

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
        self.playback_adapter = playback_adapter or QtPlaybackAdapter(
            self.video_workspace.video_output
        )
        self.playback_clock = PlaybackClock(self.playback_adapter)
        self.playback_clock.snapshot_changed.connect(self._display_playback_snapshot)
        self.video_workspace.play_pause_requested.connect(
            self.playback_clock.toggle_play_pause
        )
        self.video_workspace.seek_requested.connect(self.playback_clock.seek)
        self.playback_backend_value.setText(
            f"Playback: {self.playback_adapter.diagnostics}"
        )
        self.resize(1180, 820)
        self.refresh_recent_projects()

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

        brand = QLabel("BE")
        brand.setObjectName("Brand")
        brand_accent = QLabel("EP")
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

        project_title = QLabel("PROJECTS")
        project_title.setObjectName("SidebarTitle")
        layout.addWidget(project_title)
        layout.addWidget(self.active_project_value)
        project_actions = QHBoxLayout()
        project_actions.setSpacing(6)
        project_actions.addWidget(self.new_project_button)
        project_actions.addWidget(self.open_project_button)
        layout.addLayout(project_actions)

        recent_title = QLabel("RECENT")
        recent_title.setObjectName("SidebarTitle")
        layout.addWidget(recent_title)
        layout.addWidget(self.recent_projects_list, 1)
        layout.addStretch()

        local_label = QLabel("●  LOCAL PROCESSING")
        local_label.setObjectName("Eyebrow")
        layout.addWidget(local_label)
        return sidebar

    def _build_main_content(self) -> QWidget:
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
        transcript_header.addWidget(self.analyze_clips_button)
        transcript_header.addWidget(self.transcribe_button)
        transcript_layout.addLayout(transcript_header)
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_row.addWidget(self.search_box, 1)
        search_row.addWidget(self.match_count_label)
        search_row.addWidget(self.previous_match_button)
        search_row.addWidget(self.next_match_button)
        transcript_layout.addLayout(search_row)
        transcript_layout.addWidget(self.transcript_panel, 1)

        candidate_card = QFrame()
        candidate_card.setObjectName("Card")
        candidate_layout = QVBoxLayout(candidate_card)
        candidate_layout.setContentsMargins(20, 18, 20, 20)
        candidate_layout.setSpacing(12)
        candidate_title = QLabel("AI Clip Candidates")
        candidate_title.setObjectName("SectionTitle")
        candidate_layout.addWidget(candidate_title)
        candidate_content = QHBoxLayout()
        candidate_content.setSpacing(12)
        candidate_content.addWidget(self.candidate_list, 1)
        candidate_content.addWidget(self.candidate_details, 2)
        candidate_layout.addLayout(candidate_content)

        self.video_workspace = VideoWorkspace(
            video_card,
            transcript_card,
            candidate_card,
        )
        return self.video_workspace

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
        layout.addWidget(self.playback_backend_value)
        return status

    @Slot()
    def show_new_project_dialog(self) -> None:
        """Create a saved local project from a small modal dialog."""
        if self.repository is None:
            self.progress_label.setText("Project storage is unavailable.")
            return
        dialog = NewProjectDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.create_project(dialog.project_name.text(), dialog.brand_name.text())

    def create_project(self, name: str, brand_name: str | None = None) -> None:
        """Create and activate one empty project."""
        if self.repository is None:
            self.progress_label.setText("Project storage is unavailable.")
            return
        try:
            project = self.repository.create_project(name, brand_name)
        except ProjectStorageError as error:
            self.progress_label.setText(f"Project error: {error}")
            return
        self._clear_workspace()
        self._activate_project(project)
        self.refresh_recent_projects()
        self.progress_label.setText("Project created. Open a local VOD to begin.")

    @Slot()
    def show_open_project_dialog(self) -> None:
        """Show all locally saved projects for explicit selection."""
        if self.repository is None:
            self.progress_label.setText("Project storage is unavailable.")
            return
        try:
            projects = self.repository.list_projects()
        except ProjectStorageError as error:
            self.progress_label.setText(f"Project error: {error}")
            return
        if not projects:
            self.progress_label.setText("No saved projects. Create a project first.")
            return
        dialog = OpenProjectDialog(projects, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        project_id = dialog.selected_project_id
        if project_id is not None:
            self.open_project(project_id)

    @Slot(QListWidgetItem)
    def open_recent_project(self, item: QListWidgetItem) -> None:
        """Open a project activated from the 10-item recent list."""
        value = item.data(Qt.ItemDataRole.UserRole)
        if value is not None:
            self.open_project(str(value))

    def open_project(self, project_id: str) -> None:
        """Load a complete snapshot before replacing the active workspace."""
        if self.repository is None:
            self.progress_label.setText("Project storage is unavailable.")
            return
        try:
            snapshot = self.repository.load_project(project_id)
        except ProjectStorageError as error:
            self.progress_label.setText(f"Project error: {error}")
            return
        self._apply_project_snapshot(snapshot)
        self.refresh_recent_projects()

    def refresh_recent_projects(self) -> None:
        """Refresh the sidebar without automatically opening any project."""
        self.recent_projects_list.clear()
        if self.repository is None:
            self.recent_projects_list.addItem("No saved projects")
            self._has_saved_projects = False
            self.open_project_button.setEnabled(False)
            return
        try:
            projects = self.repository.list_recent_projects()
        except ProjectStorageError as error:
            self.recent_projects_list.addItem("Projects unavailable")
            self._has_saved_projects = False
            self.open_project_button.setEnabled(False)
            self.progress_label.setText(f"Project error: {error}")
            return
        self._has_saved_projects = bool(projects)
        self.open_project_button.setEnabled(self._has_saved_projects)
        if not projects:
            empty_item = QListWidgetItem("No saved projects")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.recent_projects_list.addItem(empty_item)
            return
        for project in projects:
            details = project.brand_name or project.filename or "No VOD selected"
            item = QListWidgetItem(f"{project.name}\n{details}")
            item.setData(Qt.ItemDataRole.UserRole, project.project_id)
            self.recent_projects_list.addItem(item)

    def _activate_project(self, project: ProjectSummary) -> None:
        self.active_project = project
        self.active_project_value.setText(project.name)
        self.open_button.setEnabled(True)

    def _set_project_switching_enabled(self, enabled: bool) -> None:
        """Prevent background results from crossing active-project boundaries."""
        self.new_project_button.setEnabled(enabled)
        self.open_project_button.setEnabled(
            enabled and self.repository is not None and self._has_saved_projects
        )
        self.recent_projects_list.setEnabled(enabled)

    def _clear_workspace(self) -> None:
        self._clear_playback(
            "Open an MP4 or MOV in the active project to enable playback."
        )
        self._video_path = None
        self._video_metadata = None
        self._video_duration = 0.0
        self._file_size_bytes = 0
        self._last_modified_at = ""
        self._file_details = ""
        self.info_panel.clear()
        self.info_panel.setPlaceholderText("Open a video to view its details.")
        self.transcript_segments = []
        self._transcript_start_seconds = ()
        self.transcript_panel.clear()
        self.search_box.clear()
        self._clear_clip_candidates()
        self.transcribe_button.setEnabled(False)
        self.use_cpu_button.setVisible(False)
        self.progress_bar.setValue(0)
        self._reset_runtime_diagnostics()

    def _apply_project_snapshot(self, snapshot: ProjectSnapshot) -> None:
        """Replace the UI only after the repository returned a valid snapshot."""
        self._clear_workspace()
        self._activate_project(snapshot.project)
        if snapshot.video is not None:
            self._restore_video(snapshot.video, snapshot.source_available)
        self._show_transcript(snapshot.transcript)
        self._show_clip_candidates(snapshot.candidates)
        self.analyze_clips_button.setEnabled(bool(snapshot.transcript))
        if snapshot.video is not None and not snapshot.source_available:
            self.progress_label.setText(
                f"Source VOD unavailable: {snapshot.video.source_path}"
            )
        else:
            self.progress_label.setText(f"Project opened: {snapshot.project.name}")

    def _restore_video(self, video: StoredVideo, source_available: bool) -> None:
        self._video_metadata = video.metadata
        self._video_duration = video.metadata.duration_seconds
        self._file_size_bytes = video.file_size_bytes
        self._last_modified_at = video.last_modified_at
        self._file_details = self._format_file_details(
            video.source_path,
            video.file_size_bytes,
            video.last_modified_at,
        )
        self.info_panel.setPlainText(
            self._format_video_details(
                self._file_details,
                video.metadata,
                source_available=source_available,
            )
        )
        self._video_path = video.source_path if source_available else None
        self.transcribe_button.setEnabled(source_available)
        if source_available:
            self._load_playback_source(video.source_path, video.metadata)
        else:
            self.video_workspace.reset_playback(
                f"Playback unavailable: source file not found at {video.source_path}"
            )

    def _load_playback_source(self, video_path: Path, metadata: VideoMetadata) -> None:
        """Map project-owned media to a neutral, transient playback source."""
        self._source_generation += 1
        self.playback_clock.clear()
        self._active_transcript_index = None
        self._active_candidate_index = None
        self._apply_match_highlights()
        self._apply_candidate_activity()

        if video_path.suffix.casefold() not in {".mp4", ".mov"}:
            self.video_workspace.reset_playback(
                "Playback unavailable: embedded playback supports MP4 and MOV. "
                "Transcription remains available for this source."
            )
            return
        if not video_path.is_file():
            self.video_workspace.reset_playback(
                f"Playback unavailable: source file not found at {video_path}"
            )
            return

        source = LocalMediaSource(
            source_id=self._source_generation,
            path=video_path,
            duration_us=seconds_to_source_us(metadata.duration_seconds),
        )
        self.playback_clock.load(source)

    def _clear_playback(self, message: str) -> None:
        """Release playback without changing persisted project data."""
        self._source_generation += 1
        self.playback_clock.clear()
        self._active_transcript_index = None
        self._active_candidate_index = None
        self.video_workspace.reset_playback(message)
        self._apply_match_highlights()
        self._apply_candidate_activity()

    @Slot(object)
    def _display_playback_snapshot(self, snapshot: PlaybackClockSnapshot) -> None:
        """Reflect one clock snapshot across all review views."""
        self.video_workspace.set_clock_snapshot(snapshot)
        position_us = snapshot.display_position_us
        transcript_index = (
            find_active_transcript_index(
                self.transcript_segments,
                position_us,
                self._transcript_start_seconds,
            )
            if snapshot.source_id is not None
            else None
        )
        candidate_index = (
            find_active_candidate_index(self.clip_candidates, position_us)
            if snapshot.source_id is not None
            else None
        )
        self._set_active_transcript_index(transcript_index)
        self._set_active_candidate_index(candidate_index)

    @Slot(int)
    def seek_to_transcript_segment(self, segment_index: int) -> None:
        """Seek to an activated transcript timestamp without altering it."""
        if segment_index < 0 or segment_index >= len(self.transcript_segments):
            return
        self._seek_to_seconds(self.transcript_segments[segment_index].start_seconds)

    @Slot(QListWidgetItem)
    def seek_to_candidate(self, item: QListWidgetItem) -> None:
        """Seek to an activated candidate's exact stored start timestamp."""
        row = self.candidate_list.row(item)
        if row < 0 or row >= len(self.clip_candidates):
            return
        self.candidate_list.setCurrentItem(item)
        self._seek_to_seconds(self.clip_candidates[row].start_seconds)

    def _seek_to_seconds(self, seconds: float) -> None:
        if not self.playback_clock.snapshot.available:
            return
        self.playback_clock.seek(seconds_to_source_us(seconds))

    def _set_active_transcript_index(self, segment_index: int | None) -> None:
        if segment_index == self._active_transcript_index:
            return
        self._active_transcript_index = segment_index
        self._apply_match_highlights()
        if segment_index is not None:
            self._scroll_transcript_block_into_view(segment_index)

    def _scroll_transcript_block_into_view(self, segment_index: int) -> None:
        block = self.transcript_panel.document().findBlockByNumber(segment_index)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        cursor_rect = self.transcript_panel.cursorRect(cursor)
        viewport_height = self.transcript_panel.viewport().height()
        if cursor_rect.top() < 0 or cursor_rect.bottom() > viewport_height:
            scroll_bar = self.transcript_panel.verticalScrollBar()
            scroll_bar.setValue(
                scroll_bar.value()
                + cursor_rect.center().y()
                - max(1, viewport_height // 2)
            )

    def _set_active_candidate_index(self, candidate_index: int | None) -> None:
        if candidate_index == self._active_candidate_index:
            return
        self._active_candidate_index = candidate_index
        self._apply_candidate_activity()

    def _apply_candidate_activity(self) -> None:
        for index in range(self.candidate_list.count()):
            item = self.candidate_list.item(index)
            base_text = item.data(CANDIDATE_BASE_TEXT_ROLE)
            if not isinstance(base_text, str):
                base_text = item.text().removeprefix("▶ ")
                item.setData(CANDIDATE_BASE_TEXT_ROLE, base_text)
            is_active = index == self._active_candidate_index
            item.setText(f"▶ {base_text}" if is_active else base_text)
            font = item.font()
            font.setWeight(QFont.Weight.DemiBold if is_active else QFont.Weight.Normal)
            item.setFont(font)
            item.setData(
                Qt.ItemDataRole.AccessibleDescriptionRole,
                "Active at the current playback time" if is_active else "",
            )

    def _show_transcript(
        self, segments: tuple[TranscriptSegment, ...] | list[TranscriptSegment]
    ) -> None:
        self.transcript_segments = list(segments)
        self._transcript_start_seconds = tuple(
            segment.start_seconds for segment in segments
        )
        self._active_transcript_index = None
        self.transcript_panel.setPlainText(
            "\n".join(
                f"[{format_timestamp(segment.start_seconds)} - "
                f"{format_timestamp(segment.end_seconds)}] {segment.text}"
                for segment in segments
            )
        )
        self.update_transcript_search(self.search_box.text())

    def _show_clip_candidates(
        self, candidates: tuple[ClipCandidate, ...] | list[ClipCandidate]
    ) -> None:
        self.clip_candidates = list(candidates)
        self._active_candidate_index = None
        self.candidate_list.clear()
        self.candidate_details.clear()
        for rank, candidate in enumerate(self.clip_candidates, start=1):
            item = QListWidgetItem(
                f"#{rank}  {candidate.score}/100  {candidate.clip_type}\n"
                f"{format_timestamp(candidate.start_seconds)} - "
                f"{format_timestamp(candidate.end_seconds)}  •  {candidate.summary}"
            )
            item.setData(CANDIDATE_BASE_TEXT_ROLE, item.text())
            item.setData(
                Qt.ItemDataRole.AccessibleTextRole,
                f"Candidate {rank}, score {candidate.score} out of 100, "
                f"{candidate.clip_type}, starts "
                f"{format_timestamp(candidate.start_seconds)}",
            )
            self.candidate_list.addItem(item)
        if self.clip_candidates:
            self.candidate_list.setCurrentRow(0)

    def _reset_runtime_diagnostics(self) -> None:
        self.device_value.setText("—")
        self.model_value.setText("—")
        self.time_value.setText("—")
        self.cuda_source_value.setText("CUDA Libraries: —")

    def open_video(self) -> None:
        """Let the user select a video and display its filesystem details."""
        if self.active_project is None:
            self.progress_label.setText(
                "Create or open a project before loading a VOD."
            )
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi)",
        )
        if not file_path:
            return

        video_path = Path(file_path)
        self.transcribe_button.setEnabled(False)
        self.progress_label.setText("Reading video metadata...")
        self.progress_bar.setValue(0)
        self.use_cpu_button.setVisible(False)
        file_details = video_path.stat()
        modified = datetime.fromtimestamp(file_details.st_mtime).astimezone()
        self._pending_video_path = video_path
        self._pending_file_size_bytes = file_details.st_size
        self._pending_last_modified_at = modified.isoformat()
        self._pending_file_details = self._format_file_details(
            video_path,
            file_details.st_size,
            modified.isoformat(),
        )
        self._previous_info_text = self.info_panel.toPlainText()
        self.info_panel.setPlainText(
            f"{self._pending_file_details}\n\nReading video metadata..."
        )
        self.open_button.setEnabled(False)
        self._set_project_switching_enabled(False)

        task = ProbeTask(video_path)
        task.signals.succeeded.connect(self.display_video_metadata)
        task.signals.failed.connect(self.display_probe_error)
        QThreadPool.globalInstance().start(task)

    @Slot(object)
    def display_video_metadata(self, metadata: VideoMetadata) -> None:
        """Display metadata returned by ffprobe."""
        video_path = self._pending_video_path
        if video_path is None:
            return
        if self.repository is not None and self.active_project is not None:
            try:
                self.repository.save_video(
                    self.active_project.project_id,
                    video_path,
                    self._pending_file_size_bytes,
                    self._pending_last_modified_at,
                    metadata,
                )
            except ProjectStorageError as error:
                self.info_panel.setPlainText(
                    f"{self._previous_info_text}\n\nProject save error: {error}"
                )
                self.progress_label.setText(f"Project save error: {error}")
                self.open_button.setEnabled(True)
                self.transcribe_button.setEnabled(self._video_path is not None)
                self._clear_pending_video()
                self._set_project_switching_enabled(True)
                return

        self._video_path = video_path
        self._video_metadata = metadata
        self._video_duration = metadata.duration_seconds
        self._file_size_bytes = self._pending_file_size_bytes
        self._last_modified_at = self._pending_last_modified_at
        self._file_details = self._pending_file_details
        self.transcript_segments = []
        self.search_box.clear()
        self.transcript_panel.clear()
        self._clear_clip_candidates()
        self._reset_runtime_diagnostics()
        self.info_panel.setPlainText(
            self._format_video_details(self._file_details, metadata)
        )
        self._load_playback_source(video_path, metadata)
        self._clear_pending_video()
        self.open_button.setEnabled(True)
        self.transcribe_button.setEnabled(True)
        self.progress_label.setText("Video metadata saved to the active project.")
        self.refresh_recent_projects()
        self._set_project_switching_enabled(True)

    @staticmethod
    def _format_file_details(
        video_path: Path, file_size_bytes: int, last_modified_at: str
    ) -> str:
        try:
            modified = datetime.fromisoformat(last_modified_at)
            modified_text = f"{modified:%Y-%m-%d %H:%M:%S %Z}".strip()
        except ValueError:
            modified_text = last_modified_at
        return "\n".join(
            (
                f"File Name: {video_path.name}",
                f"Full Path: {video_path.resolve()}",
                f"File Size (MB): {file_size_bytes / (1024 * 1024):.2f}",
                f"Last Modified Date: {modified_text}",
            )
        )

    @staticmethod
    def _format_video_details(
        file_details: str,
        metadata: VideoMetadata,
        *,
        source_available: bool = True,
    ) -> str:
        minutes, seconds = divmod(metadata.duration_seconds, 60)
        hours, minutes = divmod(int(minutes), 60)
        duration = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
        bitrate = (
            f"{metadata.bitrate_bps / 1_000_000:.2f} Mbps"
            if metadata.bitrate_bps
            else "Unknown"
        )
        details = (
            file_details,
            "",
            f"Duration: {duration}",
            f"Resolution: {metadata.width} x {metadata.height}",
            f"FPS: {metadata.fps:.3f}",
            f"Video Codec: {metadata.video_codec}",
            f"Audio Codec: {metadata.audio_codec}",
            f"Bitrate: {bitrate}",
        )
        if not source_available:
            details += ("", "Source Status: Unavailable (file missing or moved)")
        return "\n".join(details)

    def _clear_pending_video(self) -> None:
        self._pending_video_path = None
        self._pending_file_size_bytes = 0
        self._pending_last_modified_at = ""
        self._pending_file_details = ""
        self._previous_info_text = ""

    @Slot(str)
    def display_probe_error(self, message: str) -> None:
        """Display a friendly ffprobe failure message."""
        self.info_panel.setPlainText(f"{self._previous_info_text}\n\nError: {message}")
        self.open_button.setEnabled(True)
        self.transcribe_button.setEnabled(self._video_path is not None)
        self._clear_pending_video()
        self._set_project_switching_enabled(True)

    @Slot()
    def start_transcription(self, force_cpu: bool = False) -> None:
        """Start audio extraction and transcription in the thread pool."""
        if self._video_path is None:
            return

        self.open_button.setEnabled(False)
        self._set_project_switching_enabled(False)
        self.transcribe_button.setEnabled(False)
        self.analyze_clips_button.setEnabled(False)
        self.transcript_panel.clear()
        self.search_box.clear()
        self._clear_clip_candidates()
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
        self._show_transcript(result.segments)
        persistence_error: ProjectStorageError | None = None
        if self.repository is not None and self.active_project is not None:
            try:
                self.repository.replace_transcript(
                    self.active_project.project_id, result.segments
                )
            except ProjectStorageError as error:
                persistence_error = error
        self.progress_bar.setValue(100)
        elapsed_time = format_elapsed_time(result.elapsed_seconds)
        if persistence_error is None:
            suffix = " and saved" if self.active_project is not None else ""
            self.progress_label.setText(f"Transcription complete{suffix}.")
        else:
            self.progress_label.setText(
                f"Transcription complete; project save failed: {persistence_error}"
            )
        self.device_value.setText(result.compute_device.upper())
        self.model_value.setText(result.model_name)
        self.time_value.setText(elapsed_time)
        self.cuda_source_value.setText(f"CUDA Libraries: {result.cuda_library_source}")
        self.open_button.setEnabled(self.active_project is not None)
        self.transcribe_button.setEnabled(True)
        self.analyze_clips_button.setEnabled(bool(self.transcript_segments))
        self.use_cpu_button.setVisible(False)
        self._set_project_switching_enabled(True)

    def _clear_clip_candidates(self) -> None:
        """Clear candidate state when the active source or project changes."""
        self.clip_candidates = []
        self._active_candidate_index = None
        self.candidate_list.clear()
        self.candidate_details.clear()
        self.analyze_clips_button.setEnabled(False)

    @Slot()
    def start_clip_analysis(self) -> None:
        """Start local Ollama transcript analysis in the Qt thread pool."""
        if not self.transcript_segments:
            return
        self.analyze_clips_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.transcribe_button.setEnabled(False)
        self._set_project_switching_enabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Preparing local clip analysis...")

        task = ClipAnalysisTask(tuple(self.transcript_segments))
        task.signals.progressed.connect(self.display_clip_analysis_progress)
        task.signals.succeeded.connect(self.display_clip_analysis_result)
        task.signals.failed.connect(self.display_clip_analysis_error)
        QThreadPool.globalInstance().start(task)

    @Slot(int, str)
    def display_clip_analysis_progress(self, value: int, message: str) -> None:
        """Display coarse local-analysis progress while the UI remains responsive."""
        self.progress_bar.setValue(value)
        self.progress_label.setText(message)

    @Slot(object)
    def display_clip_analysis_result(self, result: ClipAnalysisResult) -> None:
        """Show complete results and persist them only for a saved project."""
        self._show_clip_candidates(result.candidates)
        persistence_error: ProjectStorageError | None = None
        if self.repository is not None and self.active_project is not None:
            try:
                self.repository.replace_candidates(
                    self.active_project.project_id, result.candidates
                )
            except ProjectStorageError as error:
                persistence_error = error
        self.progress_bar.setValue(100)
        if persistence_error is None:
            suffix = " and saved" if self.active_project is not None else ""
            self.progress_label.setText(
                f"Clip analysis complete{suffix}: "
                f"{len(self.clip_candidates)} candidates."
            )
        else:
            self.progress_label.setText(
                "Clip analysis complete in memory; project save failed: "
                f"{persistence_error}"
            )
        self.device_value.setText("OLLAMA / LOCAL")
        self.model_value.setText(result.model_name)
        self.open_button.setEnabled(self.active_project is not None)
        self.transcribe_button.setEnabled(self._video_path is not None)
        self.analyze_clips_button.setEnabled(bool(self.transcript_segments))
        self._set_project_switching_enabled(True)

    @Slot(str)
    def display_clip_analysis_error(self, message: str) -> None:
        """Restore controls after failure without replacing current candidates."""
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Clip analysis error: {message}")
        self.open_button.setEnabled(self.active_project is not None)
        self.transcribe_button.setEnabled(self._video_path is not None)
        self.analyze_clips_button.setEnabled(bool(self.transcript_segments))
        self._set_project_switching_enabled(True)

    @Slot(int)
    def display_candidate_details(self, row: int) -> None:
        """Show every required explanation field for the selected candidate."""
        if row < 0 or row >= len(self.clip_candidates):
            self.candidate_details.clear()
            return
        candidate = self.clip_candidates[row]
        signals = (
            "\n".join(f"• {item}" for item in candidate.strong_signals) or "• None"
        )
        weaknesses = "\n".join(f"• {item}" for item in candidate.weaknesses) or "• None"
        self.candidate_details.setPlainText(
            "\n".join(
                (
                    f"Start: {format_timestamp(candidate.start_seconds)}",
                    f"End: {format_timestamp(candidate.end_seconds)}",
                    f"Clip Type: {candidate.clip_type}",
                    f"Score: {candidate.score}/100",
                    "",
                    f"Summary: {candidate.summary}",
                    "",
                    f"Why BEEP selected it: {candidate.selection_reasoning}",
                    "",
                    "Strong Signals:",
                    signals,
                    "",
                    "Weaknesses / Missing Context:",
                    weaknesses,
                )
            )
        )

    @Slot(str)
    def update_transcript_search(self, query: str) -> None:
        """Highlight transcript segments matching the current search query."""
        self._match_indices = find_matching_segment_indices(
            self.transcript_segments, query
        )
        self._current_match_index = None
        has_query = bool(query)
        has_matches = bool(self._match_indices)

        if not has_query:
            self.match_count_label.setText("0 matches")
        elif has_matches:
            count = len(self._match_indices)
            noun = "match" if count == 1 else "matches"
            self.match_count_label.setText(f"{count} {noun}")
        else:
            self.match_count_label.setText("No matches")

        self.previous_match_button.setEnabled(has_matches)
        self.next_match_button.setEnabled(has_matches)
        self._rebuild_search_highlights()

    @Slot()
    def select_next_match(self) -> None:
        """Select and scroll to the next matching transcript segment."""
        self._select_match(1)

    @Slot()
    def select_previous_match(self) -> None:
        """Select and scroll to the previous matching transcript segment."""
        self._select_match(-1)

    def _select_match(self, direction: int) -> None:
        selected_index = navigate_match(
            self._match_indices, self._current_match_index, direction
        )
        if selected_index is None:
            return

        self._current_match_index = selected_index
        self._rebuild_search_highlights()
        block = self.transcript_panel.document().findBlockByNumber(selected_index)
        cursor = QTextCursor(block)
        self.transcript_panel.setTextCursor(cursor)
        self.transcript_panel.centerCursor()

    def _rebuild_search_highlights(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        document = self.transcript_panel.document()
        for segment_index in self._match_indices:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(document.findBlockByNumber(segment_index))
            selection.cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            color = (
                "#174D6B" if segment_index == self._current_match_index else "#5A1741"
            )
            selection.format.setBackground(QColor(color))
            selection.format.setProperty(
                QTextFormat.Property.FullWidthSelection,
                True,
            )
            selections.append(selection)
        self._search_selections = selections
        self._apply_match_highlights()

    def _apply_match_highlights(self) -> None:
        selections = list(self._search_selections)
        document = self.transcript_panel.document()
        active_index = self._active_transcript_index
        if active_index is not None:
            active_block = document.findBlockByNumber(active_index)
            if active_block.isValid():
                active = QTextEdit.ExtraSelection()
                active.cursor = QTextCursor(active_block)
                active.cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                if active_index not in self._match_indices:
                    active.format.setBackground(QColor("#222D42"))
                active.format.setFontUnderline(True)
                active.format.setFontWeight(int(QFont.Weight.DemiBold))
                active.format.setProperty(
                    QTextFormat.Property.FullWidthSelection,
                    True,
                )
                selections.append(active)
                segment = self.transcript_segments[active_index]
                self.transcript_panel.setAccessibleDescription(
                    "Active transcript segment from "
                    f"{format_timestamp(segment.start_seconds)} to "
                    f"{format_timestamp(segment.end_seconds)}."
                )
        else:
            self.transcript_panel.setAccessibleDescription(
                "Review transcript segments. Activate a timestamp to seek the video."
            )
        self.transcript_panel.setExtraSelections(selections)

    @Slot(str)
    def display_transcription_error(self, message: str) -> None:
        """Display a friendly transcription failure message."""
        self.progress_label.setText(f"Error: {message}")
        self.progress_bar.setValue(0)
        self.open_button.setEnabled(self.active_project is not None)
        self.transcribe_button.setEnabled(self._video_path is not None)
        self.use_cpu_button.setVisible(False)
        self._set_project_switching_enabled(True)

    @Slot(str)
    def display_cuda_runtime_error(self, message: str) -> None:
        """Explain missing CUDA components and offer a CPU retry."""
        self.progress_label.setText(f"CUDA setup error: {message}")
        self.progress_bar.setValue(0)
        self.open_button.setEnabled(self.active_project is not None)
        self.transcribe_button.setEnabled(self._video_path is not None)
        self.use_cpu_button.setVisible(self._video_path is not None)
        self.use_cpu_button.setEnabled(self._video_path is not None)
        self._set_project_switching_enabled(True)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Release native playback resources before the window closes."""
        self.playback_clock.close()
        super().closeEvent(event)


def format_timestamp(seconds: float) -> str:
    """Format seconds as a transcript timestamp."""
    whole_minutes, remaining_seconds = divmod(seconds, 60)
    hours, minutes = divmod(int(whole_minutes), 60)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:06.3f}"


def find_matching_segment_indices(
    segments: list[TranscriptSegment], query: str
) -> list[int]:
    """Return segment indices whose text contains a case-insensitive query."""
    if not query:
        return []
    normalized_query = query.casefold()
    return [
        index
        for index, segment in enumerate(segments)
        if normalized_query in segment.text.casefold()
    ]


def navigate_match(
    match_indices: list[int], current_index: int | None, direction: int
) -> int | None:
    """Move through matching segment indices, wrapping at either end."""
    if not match_indices:
        return None
    if current_index not in match_indices:
        return match_indices[0] if direction >= 0 else match_indices[-1]
    position = match_indices.index(current_index)
    step = 1 if direction >= 0 else -1
    return match_indices[(position + step) % len(match_indices)]


def format_elapsed_time(seconds: float) -> str:
    """Format an elapsed duration for the transcription summary."""
    minutes, remaining_seconds = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:05.2f}"


def create_window(repository: ProjectRepository | None = None) -> SpotlightWindow:
    """Create the main BEEP window."""
    project_repository = repository or ProjectRepository(default_database_path())
    project_repository.initialize()
    return SpotlightWindow(project_repository)


def main() -> int:
    """Run BEEP until the main window is closed."""
    application = QApplication(sys.argv)
    application.setApplicationName(APPLICATION_NAME)
    try:
        window = create_window()
    except ProjectStorageError as error:
        QMessageBox.critical(
            None,
            "BEEP Project Database Error",
            f"BEEP could not open its local project database.\n\n{error}",
        )
        return 1
    window.show()
    return application.exec()
