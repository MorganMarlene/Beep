import sqlite3
from pathlib import Path

import pytest

from spotlight.clip_detection import ClipCandidate
from spotlight.media import VideoMetadata
from spotlight.projects import (
    RECENT_PROJECT_LIMIT,
    SCHEMA_VERSION,
    ProjectRepository,
    ProjectStorageError,
    default_database_path,
)
from spotlight.transcription import TranscriptSegment


def make_repository(tmp_path: Path) -> ProjectRepository:
    repository = ProjectRepository(tmp_path / "data" / "projects.sqlite3")
    repository.initialize()
    return repository


def make_metadata(duration: float = 125.5) -> VideoMetadata:
    return VideoMetadata(
        duration_seconds=duration,
        width=1920,
        height=1080,
        fps=29.97,
        video_codec="h264",
        audio_codec="aac",
        bitrate_bps=4_500_000,
    )


def make_candidate(index: int = 0, score: int = 91) -> ClipCandidate:
    return ClipCandidate(
        start_segment=index,
        end_segment=index + 1,
        start_seconds=float(index * 5),
        end_seconds=float(index * 5 + 9),
        clip_type="deadpan humor",
        score=score,
        summary="A concise payoff.",
        selection_reasoning="The setup makes the punchline understandable.",
        strong_signals=("deadpan humor", "standalone context"),
        weaknesses=("Visual reaction was not analyzed.",),
        boundary_limited=False,
    )


def test_default_database_path_uses_local_app_data() -> None:
    path = default_database_path({"LOCALAPPDATA": r"C:\Users\Morgan\AppData\Local"})

    assert path == Path(r"C:\Users\Morgan\AppData\Local") / "BEEP" / "projects.sqlite3"


def test_initialize_creates_schema_version_one_and_is_repeatable(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    repository.initialize()

    with sqlite3.connect(repository.database_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert version == SCHEMA_VERSION
    assert tables == {"projects", "transcript_segments", "clip_candidates"}


def test_initialize_rejects_unsupported_newer_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "projects.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")

    with pytest.raises(ProjectStorageError, match="unsupported schema version"):
        ProjectRepository(database_path).initialize()


def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)

    with repository._connect() as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO transcript_segments VALUES (?, ?, ?, ?, ?)",
            ("missing", 0, 0.0, 1.0, "text"),
        )


def test_project_name_is_required_and_duplicate_names_are_distinct(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)

    with pytest.raises(ProjectStorageError, match="Project name is required"):
        repository.create_project("   ")

    first = repository.create_project("Stream One", "Morgan")
    second = repository.create_project("Stream One", "Morgan")

    assert first.name == second.name
    assert first.brand_name == "Morgan"
    assert first.project_id != second.project_id


def test_recent_projects_are_limited_to_ten(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    created = [repository.create_project(f"Project {index}") for index in range(12)]

    recent = repository.list_recent_projects(limit=50)

    assert len(recent) == RECENT_PROJECT_LIMIT
    assert [item.project_id for item in recent] == [
        item.project_id for item in reversed(created[-RECENT_PROJECT_LIMIT:])
    ]


def test_complete_project_snapshot_round_trips_exact_data(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    first = repository.create_project("第一 Stream", "BÉEP Brand")
    second = repository.create_project("Other Project")
    media_path = tmp_path / "VODs" / "Morgan's café stream.mp4"
    media_path.parent.mkdir()
    media_path.touch()
    transcript = (
        TranscriptSegment(0.125, 4.75, "  Exact opening text.  "),
        TranscriptSegment(4.75, 9.5, "Payoff — exactly preserved."),
    )
    candidates = (make_candidate(),)

    repository.save_video(
        first.project_id,
        media_path,
        file_size_bytes=123_456,
        last_modified_at="2026-08-01T10:00:00-05:00",
        metadata=make_metadata(),
    )
    repository.replace_transcript(first.project_id, transcript)
    repository.replace_candidates(first.project_id, candidates)

    snapshot = repository.load_project(first.project_id)
    other_snapshot = repository.load_project(second.project_id)

    assert snapshot.project.name == "第一 Stream"
    assert snapshot.project.brand_name == "BÉEP Brand"
    assert snapshot.video is not None
    assert snapshot.video.source_path == media_path.resolve()
    assert snapshot.video.file_size_bytes == 123_456
    assert snapshot.video.metadata == make_metadata()
    assert snapshot.transcript == transcript
    assert snapshot.candidates == candidates
    assert snapshot.source_available
    assert other_snapshot.video is None
    assert other_snapshot.transcript == ()
    assert other_snapshot.candidates == ()


def test_restoration_removes_only_exact_persisted_segment_duplicates(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    project = repository.create_project("Duplicate transcript")
    with repository._connect() as connection:
        connection.executemany(
            "INSERT INTO transcript_segments "
            "(project_id, segment_index, start_seconds, end_seconds, text) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                (project.project_id, 0, 10.0, 12.0, "Can you hear me?"),
                (project.project_id, 1, 10.0, 12.0, "Can you hear me?"),
                (project.project_id, 2, 20.0, 22.0, "Can you hear me?"),
            ),
        )

    snapshot = repository.load_project(project.project_id)

    assert snapshot.transcript == (
        TranscriptSegment(10.0, 12.0, "Can you hear me?"),
        TranscriptSegment(20.0, 22.0, "Can you hear me?"),
    )


def test_source_change_clears_derived_rows_atomically(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    project = repository.create_project("Source change")
    first_path = tmp_path / "first.mp4"
    second_path = tmp_path / "second.mp4"
    first_path.touch()
    second_path.touch()
    repository.save_video(project.project_id, first_path, 10, "first", make_metadata())
    repository.replace_transcript(
        project.project_id, (TranscriptSegment(0.0, 1.0, "Old"),)
    )
    repository.replace_candidates(project.project_id, (make_candidate(),))

    repository.save_video(
        project.project_id, second_path, 20, "second", make_metadata()
    )
    snapshot = repository.load_project(project.project_id)

    assert snapshot.video is not None
    assert snapshot.video.source_path == second_path.resolve()
    assert snapshot.transcript == ()
    assert snapshot.candidates == ()


def test_failed_replacements_preserve_previous_complete_data(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    project = repository.create_project("Atomic")
    transcript = (TranscriptSegment(0.0, 1.0, "Saved"),)
    candidate = make_candidate()
    repository.replace_transcript(project.project_id, transcript)
    repository.replace_candidates(project.project_id, (candidate,))

    with pytest.raises(ProjectStorageError, match="Could not save the transcript"):
        repository.replace_transcript(
            project.project_id, (TranscriptSegment(2.0, 1.0, "Invalid"),)
        )
    with pytest.raises(ProjectStorageError, match="Could not save clip candidates"):
        repository.replace_candidates(project.project_id, (make_candidate(score=101),))

    snapshot = repository.load_project(project.project_id)
    assert snapshot.transcript == transcript
    assert snapshot.candidates == (candidate,)


def test_invalid_candidate_json_rejects_complete_snapshot(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    project = repository.create_project("Invalid JSON")
    repository.replace_candidates(project.project_id, (make_candidate(),))
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE clip_candidates SET strong_signals_json = ? WHERE project_id = ?",
            ('{"not": "a list"}', project.project_id),
        )

    with pytest.raises(ProjectStorageError, match="JSON list of text"):
        repository.load_project(project.project_id)


def test_missing_media_does_not_discard_review_data(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    project = repository.create_project("Missing source")
    missing_path = tmp_path / "moved.mp4"
    repository.save_video(project.project_id, missing_path, 10, "old", make_metadata())
    repository.replace_transcript(
        project.project_id, (TranscriptSegment(0.0, 1.0, "Still useful"),)
    )
    repository.replace_candidates(project.project_id, (make_candidate(),))

    snapshot = repository.load_project(project.project_id)

    assert not snapshot.source_available
    assert snapshot.transcript[0].text == "Still useful"
    assert snapshot.candidates == (make_candidate(),)
