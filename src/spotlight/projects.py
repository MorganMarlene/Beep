"""Local SQLite persistence for BEEP projects."""

import json
import os
import sqlite3
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from spotlight.clip_detection import ClipCandidate
from spotlight.media import VideoMetadata
from spotlight.transcription import TranscriptSegment, remove_exact_duplicate_segments

SCHEMA_VERSION = 1
RECENT_PROJECT_LIMIT = 10
Migration = Callable[[sqlite3.Connection], None]
FUTURE_MIGRATIONS: tuple[tuple[int, Migration], ...] = ()


class ProjectStorageError(Exception):
    """Raised when local project data cannot be stored or restored safely."""


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    """Small project identity used by recent and open-project lists."""

    project_id: str
    name: str
    brand_name: str | None
    filename: str | None
    created_at: str
    updated_at: str
    last_opened_at: str


@dataclass(frozen=True, slots=True)
class StoredVideo:
    """A path and its last successfully probed display metadata."""

    source_path: Path
    filename: str
    file_size_bytes: int
    last_modified_at: str
    metadata: VideoMetadata


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    """Complete immutable state restored before the active UI is replaced."""

    project: ProjectSummary
    video: StoredVideo | None
    transcript: tuple[TranscriptSegment, ...]
    candidates: tuple[ClipCandidate, ...]

    @property
    def source_available(self) -> bool:
        """Return whether the stored original VOD is currently accessible."""
        return self.video is not None and self.video.source_path.is_file()


def default_database_path(environment: dict[str, str] | None = None) -> Path:
    """Return BEEP's per-user Windows database path."""
    values = environment if environment is not None else os.environ
    local_app_data = values.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "BEEP" / "projects.sqlite3"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _decode_text_list(raw_value: str, field_name: str) -> tuple[str, ...]:
    try:
        value: object = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise ProjectStorageError(
            f"Stored candidate {field_name} contains invalid JSON."
        ) from error
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProjectStorageError(
            f"Stored candidate {field_name} must be a JSON list of text values."
        )
    return tuple(value)


class ProjectRepository:
    """Explicit data-access boundary for the local project database."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        """Create schema version 1 or accept the current supported schema."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                current_version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
                if current_version > SCHEMA_VERSION:
                    raise ProjectStorageError(
                        "The BEEP project database uses unsupported schema version "
                        f"{current_version}; this build supports version "
                        f"{SCHEMA_VERSION}."
                    )
                if current_version == 0:
                    self._create_schema_v1(connection)
                elif current_version < SCHEMA_VERSION:
                    self._apply_future_migrations(connection, current_version)
        except sqlite3.Error as error:
            raise ProjectStorageError(
                f"Could not initialize the local project database: {error}"
            ) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _create_schema_v1(connection: sqlite3.Connection) -> None:
        statements = (
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                brand_name TEXT,
                source_path TEXT,
                filename TEXT,
                file_size_bytes INTEGER,
                last_modified_at TEXT,
                duration_seconds REAL,
                width INTEGER,
                height INTEGER,
                fps REAL,
                video_codec TEXT,
                audio_codec TEXT,
                bitrate_bps INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_opened_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE transcript_segments (
                project_id TEXT NOT NULL,
                segment_index INTEGER NOT NULL CHECK (segment_index >= 0),
                start_seconds REAL NOT NULL CHECK (start_seconds >= 0),
                end_seconds REAL NOT NULL CHECK (end_seconds >= start_seconds),
                text TEXT NOT NULL,
                PRIMARY KEY (project_id, segment_index),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE clip_candidates (
                project_id TEXT NOT NULL,
                rank INTEGER NOT NULL CHECK (rank >= 0),
                start_segment INTEGER NOT NULL CHECK (start_segment >= 0),
                end_segment INTEGER NOT NULL CHECK (end_segment >= start_segment),
                start_seconds REAL NOT NULL CHECK (start_seconds >= 0),
                end_seconds REAL NOT NULL CHECK (end_seconds > start_seconds),
                clip_type TEXT NOT NULL,
                score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
                summary TEXT NOT NULL,
                selection_reasoning TEXT NOT NULL,
                strong_signals_json TEXT NOT NULL,
                weaknesses_json TEXT NOT NULL,
                boundary_limited INTEGER NOT NULL CHECK (boundary_limited IN (0, 1)),
                PRIMARY KEY (project_id, rank),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """,
            "CREATE INDEX transcript_project_order ON "
            "transcript_segments(project_id, segment_index)",
            "CREATE INDEX candidate_project_rank ON clip_candidates(project_id, rank)",
            "CREATE INDEX project_recent_order ON "
            "projects(last_opened_at DESC, updated_at DESC)",
        )
        try:
            for statement in statements:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except sqlite3.Error:
            connection.rollback()
            raise

    @staticmethod
    def _apply_future_migrations(
        connection: sqlite3.Connection, current_version: int
    ) -> None:
        version = current_version
        for target_version, migration in FUTURE_MIGRATIONS:
            if target_version <= version:
                continue
            if target_version != version + 1:
                break
            migration(connection)
            version = target_version
            connection.execute(f"PRAGMA user_version = {version}")
        if version != SCHEMA_VERSION:
            raise ProjectStorageError(
                f"No migration path exists from schema version {current_version} "
                f"to {SCHEMA_VERSION}."
            )

    def create_project(
        self, name: str, brand_name: str | None = None
    ) -> ProjectSummary:
        """Create and return a saved empty project."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ProjectStorageError("Project name is required.")
        cleaned_brand = brand_name.strip() if brand_name else None
        cleaned_brand = cleaned_brand or None
        project_id = str(uuid.uuid4())
        timestamp = _utc_now()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO projects (
                        id, name, brand_name, created_at, updated_at, last_opened_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        cleaned_name,
                        cleaned_brand,
                        timestamp,
                        timestamp,
                        timestamp,
                    ),
                )
        except sqlite3.Error as error:
            raise ProjectStorageError(
                f"Could not create the project: {error}"
            ) from error
        return ProjectSummary(
            project_id,
            cleaned_name,
            cleaned_brand,
            None,
            timestamp,
            timestamp,
            timestamp,
        )

    def list_recent_projects(
        self, limit: int = RECENT_PROJECT_LIMIT
    ) -> tuple[ProjectSummary, ...]:
        """Return at most 10 recent projects in deterministic order."""
        bounded_limit = min(max(limit, 0), RECENT_PROJECT_LIMIT)
        return self._list_projects(limit=bounded_limit)

    def list_projects(self) -> tuple[ProjectSummary, ...]:
        """Return all projects for the local Open Project dialog."""
        return self._list_projects(limit=None)

    def _list_projects(self, limit: int | None) -> tuple[ProjectSummary, ...]:
        query = (
            "SELECT id, name, brand_name, filename, created_at, updated_at, "
            "last_opened_at FROM projects ORDER BY last_opened_at DESC, "
            "updated_at DESC, id ASC"
        )
        parameters: tuple[int, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            parameters = (limit,)
        try:
            with self._connect() as connection:
                rows = connection.execute(query, parameters).fetchall()
        except sqlite3.Error as error:
            raise ProjectStorageError(f"Could not list projects: {error}") from error
        return tuple(self._summary_from_row(row) for row in rows)

    def load_project(self, project_id: str) -> ProjectSnapshot:
        """Load and validate a complete snapshot, then record it as opened."""
        try:
            with self._connect() as connection:
                project_row = connection.execute(
                    "SELECT * FROM projects WHERE id = ?", (project_id,)
                ).fetchone()
                if project_row is None:
                    raise ProjectStorageError("The selected project no longer exists.")
                transcript_rows = connection.execute(
                    "SELECT start_seconds, end_seconds, text FROM "
                    "transcript_segments WHERE project_id = ? ORDER BY segment_index",
                    (project_id,),
                ).fetchall()
                candidate_rows = connection.execute(
                    "SELECT * FROM clip_candidates WHERE project_id = ? ORDER BY rank",
                    (project_id,),
                ).fetchall()
                snapshot = self._snapshot_from_rows(
                    project_row, transcript_rows, candidate_rows
                )
                opened_at = _utc_now()
                connection.execute(
                    "UPDATE projects SET last_opened_at = ? WHERE id = ?",
                    (opened_at, project_id),
                )
        except ProjectStorageError:
            raise
        except sqlite3.Error as error:
            raise ProjectStorageError(f"Could not open the project: {error}") from error
        return replace(
            snapshot,
            project=replace(snapshot.project, last_opened_at=opened_at),
        )

    @staticmethod
    def _summary_from_row(row: sqlite3.Row) -> ProjectSummary:
        return ProjectSummary(
            project_id=str(row["id"]),
            name=str(row["name"]),
            brand_name=(str(row["brand_name"]) if row["brand_name"] else None),
            filename=(str(row["filename"]) if row["filename"] else None),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            last_opened_at=str(row["last_opened_at"]),
        )

    def _snapshot_from_rows(
        self,
        project_row: sqlite3.Row,
        transcript_rows: Sequence[sqlite3.Row],
        candidate_rows: Sequence[sqlite3.Row],
    ) -> ProjectSnapshot:
        video = None
        if project_row["source_path"] is not None:
            required_video_fields = (
                "filename",
                "file_size_bytes",
                "last_modified_at",
                "duration_seconds",
                "width",
                "height",
                "fps",
                "video_codec",
                "audio_codec",
                "bitrate_bps",
            )
            if any(project_row[field] is None for field in required_video_fields):
                raise ProjectStorageError(
                    "Stored project video metadata is incomplete."
                )
            video = StoredVideo(
                source_path=Path(str(project_row["source_path"])),
                filename=str(project_row["filename"]),
                file_size_bytes=int(project_row["file_size_bytes"]),
                last_modified_at=str(project_row["last_modified_at"]),
                metadata=VideoMetadata(
                    duration_seconds=float(project_row["duration_seconds"]),
                    width=int(project_row["width"]),
                    height=int(project_row["height"]),
                    fps=float(project_row["fps"]),
                    video_codec=str(project_row["video_codec"]),
                    audio_codec=str(project_row["audio_codec"]),
                    bitrate_bps=int(project_row["bitrate_bps"]),
                ),
            )
        transcript = tuple(
            remove_exact_duplicate_segments(
                tuple(
                    TranscriptSegment(
                        start_seconds=float(row["start_seconds"]),
                        end_seconds=float(row["end_seconds"]),
                        text=str(row["text"]),
                    )
                    for row in transcript_rows
                )
            )
        )
        candidates = tuple(
            ClipCandidate(
                start_segment=int(row["start_segment"]),
                end_segment=int(row["end_segment"]),
                start_seconds=float(row["start_seconds"]),
                end_seconds=float(row["end_seconds"]),
                clip_type=str(row["clip_type"]),
                score=int(row["score"]),
                summary=str(row["summary"]),
                selection_reasoning=str(row["selection_reasoning"]),
                strong_signals=_decode_text_list(
                    str(row["strong_signals_json"]), "strong signals"
                ),
                weaknesses=_decode_text_list(str(row["weaknesses_json"]), "weaknesses"),
                boundary_limited=bool(row["boundary_limited"]),
            )
            for row in candidate_rows
        )
        return ProjectSnapshot(
            self._summary_from_row(project_row), video, transcript, candidates
        )

    def save_video(
        self,
        project_id: str,
        source_path: Path,
        file_size_bytes: int,
        last_modified_at: str,
        metadata: VideoMetadata,
    ) -> None:
        """Save probed metadata and clear derived state when the source changes."""
        timestamp = _utc_now()
        source = str(source_path.resolve())
        try:
            with self._connect() as connection:
                existing = connection.execute(
                    "SELECT source_path FROM projects WHERE id = ?", (project_id,)
                ).fetchone()
                if existing is None:
                    raise ProjectStorageError("The active project no longer exists.")
                source_changed = existing["source_path"] != source
                connection.execute(
                    """
                    UPDATE projects SET
                        source_path = ?, filename = ?, file_size_bytes = ?,
                        last_modified_at = ?, duration_seconds = ?, width = ?,
                        height = ?, fps = ?, video_codec = ?, audio_codec = ?,
                        bitrate_bps = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        source,
                        source_path.name,
                        file_size_bytes,
                        last_modified_at,
                        metadata.duration_seconds,
                        metadata.width,
                        metadata.height,
                        metadata.fps,
                        metadata.video_codec,
                        metadata.audio_codec,
                        metadata.bitrate_bps,
                        timestamp,
                        project_id,
                    ),
                )
                if source_changed:
                    connection.execute(
                        "DELETE FROM transcript_segments WHERE project_id = ?",
                        (project_id,),
                    )
                    connection.execute(
                        "DELETE FROM clip_candidates WHERE project_id = ?",
                        (project_id,),
                    )
        except ProjectStorageError:
            raise
        except sqlite3.Error as error:
            raise ProjectStorageError(
                f"Could not save video metadata: {error}"
            ) from error

    def replace_transcript(
        self, project_id: str, segments: Sequence[TranscriptSegment]
    ) -> None:
        """Atomically replace one project's complete transcript."""
        timestamp = _utc_now()
        rows = tuple(
            (project_id, index, item.start_seconds, item.end_seconds, item.text)
            for index, item in enumerate(remove_exact_duplicate_segments(segments))
        )
        try:
            with self._connect() as connection:
                self._require_project(connection, project_id)
                connection.execute(
                    "DELETE FROM transcript_segments WHERE project_id = ?",
                    (project_id,),
                )
                connection.executemany(
                    "INSERT INTO transcript_segments (project_id, segment_index, "
                    "start_seconds, end_seconds, text) VALUES (?, ?, ?, ?, ?)",
                    rows,
                )
                connection.execute(
                    "UPDATE projects SET updated_at = ? WHERE id = ?",
                    (timestamp, project_id),
                )
        except ProjectStorageError:
            raise
        except sqlite3.Error as error:
            raise ProjectStorageError(
                f"Could not save the transcript: {error}"
            ) from error

    def replace_candidates(
        self, project_id: str, candidates: Sequence[ClipCandidate]
    ) -> None:
        """Atomically replace one project's complete validated candidate set."""
        timestamp = _utc_now()
        rows = tuple(
            (
                project_id,
                rank,
                item.start_segment,
                item.end_segment,
                item.start_seconds,
                item.end_seconds,
                item.clip_type,
                item.score,
                item.summary,
                item.selection_reasoning,
                json.dumps(item.strong_signals, ensure_ascii=False),
                json.dumps(item.weaknesses, ensure_ascii=False),
                int(item.boundary_limited),
            )
            for rank, item in enumerate(candidates)
        )
        try:
            with self._connect() as connection:
                self._require_project(connection, project_id)
                connection.execute(
                    "DELETE FROM clip_candidates WHERE project_id = ?", (project_id,)
                )
                connection.executemany(
                    """
                    INSERT INTO clip_candidates (
                        project_id, rank, start_segment, end_segment, start_seconds,
                        end_seconds, clip_type, score, summary, selection_reasoning,
                        strong_signals_json, weaknesses_json, boundary_limited
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                connection.execute(
                    "UPDATE projects SET updated_at = ? WHERE id = ?",
                    (timestamp, project_id),
                )
        except ProjectStorageError:
            raise
        except sqlite3.Error as error:
            raise ProjectStorageError(
                f"Could not save clip candidates: {error}"
            ) from error

    @staticmethod
    def _require_project(connection: sqlite3.Connection, project_id: str) -> None:
        exists = connection.execute(
            "SELECT 1 FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if exists is None:
            raise ProjectStorageError("The active project no longer exists.")
