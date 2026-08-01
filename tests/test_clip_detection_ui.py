import os
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from spotlight.app import ClipAnalysisTask, SpotlightWindow  # noqa: E402
from spotlight.clip_detection import (  # noqa: E402
    ClipAnalysisError,
    ClipAnalysisResult,
    ClipCandidate,
)
from spotlight.transcription import TranscriptionResult, TranscriptSegment  # noqa: E402


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])


def make_transcription_result() -> TranscriptionResult:
    return TranscriptionResult(
        segments=[TranscriptSegment(0.0, 5.0, "A complete funny moment")],
        compute_device="cpu",
        model_name="base",
        elapsed_seconds=1.0,
        cuda_library_source="Not used (CPU)",
    )


def make_candidate(index: int, score: int) -> ClipCandidate:
    return ClipCandidate(
        start_segment=index,
        end_segment=index,
        start_seconds=float(index * 10),
        end_seconds=float(index * 10 + 8),
        clip_type="deadpan humor",
        score=score,
        summary=f"Candidate {index}",
        selection_reasoning="The line has a complete setup and payoff.",
        strong_signals=("deadpan humor", "standalone context"),
        weaknesses=("Visual reaction was not analyzed.",),
    )


def test_analysis_control_requires_completed_transcript(
    application: QApplication,
) -> None:
    window = SpotlightWindow()

    assert not window.analyze_clips_button.isEnabled()

    window.display_transcript(make_transcription_result())

    assert window.analyze_clips_button.isEnabled()
    window.close()


def test_ranked_results_show_all_candidate_details(
    application: QApplication,
) -> None:
    window = SpotlightWindow()
    window.display_transcript(make_transcription_result())
    result = ClipAnalysisResult(
        candidates=(make_candidate(0, 95), make_candidate(1, 80)),
        model_name="qwen2.5:7b",
    )

    window.display_clip_analysis_result(result)

    assert window.candidate_list.count() == 2
    assert "95/100" in window.candidate_list.item(0).text()
    details = window.candidate_details.toPlainText()
    for expected in (
        "Start:",
        "End:",
        "Clip Type:",
        "Score:",
        "Summary:",
        "Why BEEP selected it:",
        "Strong Signals:",
        "Weaknesses / Missing Context:",
        "Visual reaction was not analyzed.",
    ):
        assert expected in details
    window.close()


def test_analysis_failure_preserves_current_in_memory_results(
    application: QApplication,
) -> None:
    window = SpotlightWindow()
    window.display_transcript(make_transcription_result())
    result = ClipAnalysisResult((make_candidate(0, 90),), "qwen2.5:7b")
    window.display_clip_analysis_result(result)

    window.display_clip_analysis_error("Ollama is unavailable")

    assert window.clip_candidates == list(result.candidates)
    assert window.candidate_list.count() == 1
    assert window.analyze_clips_button.isEnabled()
    assert "Ollama is unavailable" in window.progress_label.text()
    window.close()


def test_candidate_state_clears_with_active_source(
    application: QApplication,
) -> None:
    window = SpotlightWindow()
    window.display_transcript(make_transcription_result())
    window.display_clip_analysis_result(
        ClipAnalysisResult((make_candidate(0, 90),), "qwen2.5:7b")
    )

    window._clear_clip_candidates()

    assert window.clip_candidates == []
    assert window.candidate_list.count() == 0
    assert not window.analyze_clips_button.isEnabled()
    window.close()


def test_long_candidate_list_remains_scrollable(application: QApplication) -> None:
    window = SpotlightWindow()
    window.resize(960, 700)
    window.show()
    application.processEvents()
    candidates = tuple(make_candidate(index, 100 - index) for index in range(30))

    window.display_clip_analysis_result(ClipAnalysisResult(candidates, "qwen2.5:7b"))
    application.processEvents()

    assert window.candidate_list.count() == 30
    assert window.candidate_list.verticalScrollBar().maximum() > 0
    window.close()


def test_background_task_reports_success_without_mutating_transcript() -> None:
    segments = (TranscriptSegment(0.0, 5.0, "Original text"),)
    expected = ClipAnalysisResult((make_candidate(0, 90),), "qwen2.5:7b")
    successes: list[object] = []
    task = ClipAnalysisTask(segments)
    task.signals.succeeded.connect(successes.append)

    with patch("spotlight.app.analyze_transcript", return_value=expected):
        task.run()

    assert successes == [expected]
    assert segments[0].text == "Original text"


def test_background_task_reports_failure() -> None:
    task = ClipAnalysisTask((TranscriptSegment(0.0, 5.0, "Original text"),))
    failures: list[str] = []
    task.signals.failed.connect(failures.append)

    with patch(
        "spotlight.app.analyze_transcript",
        side_effect=ClipAnalysisError("local failure"),
    ):
        task.run()

    assert failures == ["local failure"]
