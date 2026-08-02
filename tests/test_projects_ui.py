import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from spotlight.app import NewProjectDialog, SpotlightWindow  # noqa: E402
from spotlight.clip_detection import ClipAnalysisResult, ClipCandidate  # noqa: E402
from spotlight.media import VideoMetadata  # noqa: E402
from spotlight.projects import ProjectRepository, ProjectStorageError  # noqa: E402
from spotlight.transcription import (  # noqa: E402
    TranscriptionResult,
    TranscriptSegment,
)


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])


@pytest.fixture
def repository(tmp_path: Path) -> ProjectRepository:
    result = ProjectRepository(tmp_path / "projects.sqlite3")
    result.initialize()
    return result


def make_candidate(score: int = 92) -> ClipCandidate:
    return ClipCandidate(
        start_segment=0,
        end_segment=0,
        start_seconds=0.0,
        end_seconds=5.0,
        clip_type="funny dialogue",
        score=score,
        summary="A complete joke.",
        selection_reasoning="It has setup and payoff.",
        strong_signals=("funny dialogue",),
        weaknesses=("Visual context unavailable.",),
    )


def make_transcription() -> TranscriptionResult:
    return TranscriptionResult(
        segments=[TranscriptSegment(0.0, 5.0, "Exact transcript text")],
        compute_device="cpu",
        model_name="base",
        elapsed_seconds=1.0,
        cuda_library_source="Not used (CPU)",
    )


def make_metadata() -> VideoMetadata:
    return VideoMetadata(5.0, 1920, 1080, 30.0, "h264", "aac", 4_000_000)


def test_new_project_requires_name(application: QApplication) -> None:
    dialog = NewProjectDialog()

    dialog.project_name.setText("   ")
    dialog.accept()

    assert dialog.result() == 0
    assert dialog.validation_label.text() == "Project name is required."
    dialog.close()


def test_project_actions_require_an_active_project(
    application: QApplication, repository: ProjectRepository
) -> None:
    window = SpotlightWindow(repository)

    assert window.active_project is None
    assert window.active_project_value.text() == "No active project"
    assert not window.open_button.isEnabled()

    window.create_project("Launch Stream", "BEEP Brand")

    assert window.active_project is not None
    assert window.active_project.name == "Launch Stream"
    assert window.active_project.brand_name == "BEEP Brand"
    assert window.active_project_value.text() == "Launch Stream"
    assert window.open_button.isEnabled()
    window.close()


def test_sidebar_recent_projects_are_limited_to_ten(
    application: QApplication, repository: ProjectRepository
) -> None:
    window = SpotlightWindow(repository)
    for index in range(12):
        window.create_project(f"Project {index}")

    window.refresh_recent_projects()

    assert window.recent_projects_list.count() == 10
    assert window.recent_projects_list.item(0).text().startswith("Project 11")
    window.close()


def test_saved_transcript_and_candidates_restore_after_restart(
    application: QApplication, repository: ProjectRepository
) -> None:
    first_window = SpotlightWindow(repository)
    first_window.create_project("Persistent Project")
    assert first_window.active_project is not None
    project_id = first_window.active_project.project_id
    first_window.display_transcript(make_transcription())
    first_window.display_clip_analysis_result(
        ClipAnalysisResult((make_candidate(),), "qwen2.5:7b")
    )
    first_window.close()

    second_window = SpotlightWindow(repository)
    assert second_window.active_project is None
    second_window.open_project(project_id)

    assert second_window.transcript_segments == make_transcription().segments
    assert second_window.clip_candidates == [make_candidate()]
    assert "Exact transcript text" in second_window.transcript_panel.toPlainText()
    assert second_window.candidate_list.count() == 1
    second_window.close()


def test_failed_project_load_preserves_active_workspace(
    application: QApplication, repository: ProjectRepository
) -> None:
    good = repository.create_project("Good Project")
    bad = repository.create_project("Bad Project")
    repository.replace_candidates(bad.project_id, (make_candidate(),))
    window = SpotlightWindow(repository)
    window.open_project(good.project_id)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "UPDATE clip_candidates SET weaknesses_json = ? WHERE project_id = ?",
            ("not-json", bad.project_id),
        )

    window.open_project(bad.project_id)

    assert window.active_project is not None
    assert window.active_project.project_id == good.project_id
    assert "invalid JSON" in window.progress_label.text()
    window.close()


def test_missing_vod_restores_review_data_and_disables_media_actions(
    application: QApplication, repository: ProjectRepository, tmp_path: Path
) -> None:
    project = repository.create_project("Moved VOD")
    missing_path = tmp_path / "missing.mp4"
    repository.save_video(project.project_id, missing_path, 100, "old", make_metadata())
    repository.replace_transcript(project.project_id, make_transcription().segments)
    repository.replace_candidates(project.project_id, (make_candidate(),))
    window = SpotlightWindow(repository)

    window.open_project(project.project_id)

    assert window._video_path is None
    assert not window.transcribe_button.isEnabled()
    assert window.analyze_clips_button.isEnabled()
    assert "Source Status: Unavailable" in window.info_panel.toPlainText()
    assert str(missing_path) in window.progress_label.text()
    window.close()


def test_unsaved_candidate_results_remain_in_memory_only(
    application: QApplication,
) -> None:
    window = SpotlightWindow()

    window.display_transcript(make_transcription())
    window.display_clip_analysis_result(
        ClipAnalysisResult((make_candidate(),), "qwen2.5:7b")
    )

    assert window.active_project is None
    assert window.clip_candidates == [make_candidate()]
    assert "saved" not in window.progress_label.text().casefold()
    window.close()


def test_candidate_save_failure_keeps_new_result_in_memory_and_old_result_saved(
    application: QApplication, repository: ProjectRepository
) -> None:
    window = SpotlightWindow(repository)
    window.create_project("Candidate recovery")
    assert window.active_project is not None
    project_id = window.active_project.project_id
    previous = make_candidate(80)
    current = make_candidate(95)
    repository.replace_candidates(project_id, (previous,))

    with patch.object(
        repository,
        "replace_candidates",
        side_effect=ProjectStorageError("database locked"),
    ):
        window.display_clip_analysis_result(
            ClipAnalysisResult((current,), "qwen2.5:7b")
        )

    assert window.clip_candidates == [current]
    assert repository.load_project(project_id).candidates == (previous,)
    assert "database locked" in window.progress_label.text()
    window.close()


def test_partial_analysis_stays_in_memory_and_preserves_complete_saved_candidates(
    application: QApplication, repository: ProjectRepository
) -> None:
    window = SpotlightWindow(repository)
    window.create_project("Partial analysis recovery")
    assert window.active_project is not None
    project_id = window.active_project.project_id
    previous = make_candidate(80)
    partial = make_candidate(95)
    repository.replace_candidates(project_id, (previous,))

    window.display_clip_analysis_result(
        ClipAnalysisResult(
            (partial,),
            "qwen2.5:7b",
            ("Batch 2 of 4 failed: request timed out",),
        )
    )

    assert window.clip_candidates == [partial]
    assert repository.load_project(project_id).candidates == (previous,)
    assert "Batch 2 of 4 failed" in window.progress_label.text()
    assert "kept in memory" in window.progress_label.text()
    window.close()
