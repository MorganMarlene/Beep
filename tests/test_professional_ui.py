import os
import time
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from spotlight.app import SpotlightWindow  # noqa: E402
from spotlight.clip_detection import ClipCandidate  # noqa: E402
from spotlight.theme import (  # noqa: E402
    BACKGROUND,
    BLUE_ACCENT,
    BODY_POINT_SIZE,
    DISPLAY_POINT_SIZE,
    HEADER_EXPANDED_HEIGHT,
    MOTION_DEFAULT_MS,
    MOTION_MAX_MS,
    MOTION_MIN_MS,
    PINK_ACCENT,
    SECTION_POINT_SIZE,
    SIDEBAR_EXPANDED_MAX,
    SIDEBAR_EXPANDED_MIN,
    SPACING_SCALE,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TYPOGRAPHY_LEVELS,
    GradientWordmark,
    MotionController,
    contrast_ratio,
    reduced_motion_requested,
)
from spotlight.transcription import TranscriptSegment  # noqa: E402


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])


def make_candidate() -> ClipCandidate:
    return ClipCandidate(
        start_segment=0,
        end_segment=1,
        start_seconds=10.0,
        end_seconds=24.0,
        clip_type="deadpan humor",
        score=94,
        summary="A dry setup lands with a clear punchline.",
        selection_reasoning="The exchange contains a complete setup and payoff.",
        strong_signals=("memorable quote", "standalone context"),
        weaknesses=("Visual context was not analyzed.",),
    )


def test_theme_uses_one_8_point_scale_and_three_typography_levels() -> None:
    assert all(value % 8 == 0 for value in SPACING_SCALE)
    assert TYPOGRAPHY_LEVELS == ("display", "section", "body")
    assert len({DISPLAY_POINT_SIZE, SECTION_POINT_SIZE, BODY_POINT_SIZE}) == 3
    assert DISPLAY_POINT_SIZE > SECTION_POINT_SIZE > BODY_POINT_SIZE


def test_theme_color_pairs_meet_readability_targets() -> None:
    assert contrast_ratio(TEXT_PRIMARY, BACKGROUND) >= 4.5
    assert contrast_ratio(TEXT_PRIMARY, SURFACE) >= 4.5
    assert contrast_ratio(TEXT_MUTED, BACKGROUND) >= 4.5
    assert contrast_ratio(BLUE_ACCENT, BACKGROUND) >= 3
    assert contrast_ratio(PINK_ACCENT, BACKGROUND) >= 3


def test_gradient_wordmark_is_accessible_and_contains_no_white(
    application: QApplication,
) -> None:
    wordmark = GradientWordmark()

    assert wordmark.text() == "BEEP"
    assert wordmark.accessibleName() == "BEEP"
    assert wordmark.gradient_colors == (BLUE_ACCENT, PINK_ACCENT)
    assert "#FFFFFF" not in wordmark.gradient_colors
    assert wordmark.sizeHint().width() > 0
    assert wordmark.focusPolicy() == Qt.FocusPolicy.NoFocus
    wordmark.close()


def test_reduced_motion_honors_explicit_local_override() -> None:
    with patch.dict(os.environ, {"BEEP_REDUCED_MOTION": "1"}):
        assert reduced_motion_requested()
    with patch.dict(os.environ, {"BEEP_REDUCED_MOTION": "0"}):
        assert not reduced_motion_requested()


def test_motion_is_bounded_coalesced_and_releases_resources(
    application: QApplication,
) -> None:
    label = QLabel("Status")
    label.show()
    controller = MotionController(reduced_motion=False)

    assert MOTION_MIN_MS <= MOTION_DEFAULT_MS <= MOTION_MAX_MS
    assert controller.fade_in(label, duration_ms=1)
    assert controller.fade_in(label, duration_ms=10_000)
    assert controller.active_animation_count == 1
    QTest.qWait(MOTION_MAX_MS + 40)
    application.processEvents()

    assert controller.active_animation_count == 0
    assert label.graphicsEffect() is None
    label.close()


def test_reduced_motion_applies_final_state_without_animation(
    application: QApplication,
) -> None:
    label = QLabel("Immediate")
    label.show()
    controller = MotionController(reduced_motion=True)

    assert not controller.fade_in(label)
    assert controller.active_animation_count == 0
    assert label.graphicsEffect() is None
    label.close()


def test_responsive_layout_preserves_state_and_widget_identity(
    application: QApplication,
) -> None:
    window = SpotlightWindow()
    window._show_transcript(
        (
            TranscriptSegment(0.0, 4.0, "Exact first line"),
            TranscriptSegment(5.0, 9.0, "Exact searchable line"),
        )
    )
    window._show_clip_candidates((make_candidate(),))
    window.search_box.setText("searchable")
    window.progress_bar.setValue(37)
    window.show()
    application.processEvents()
    identities = {
        "video": id(window.video_workspace.video_output),
        "transcript": id(window.transcript_panel),
        "candidates": id(window.candidate_list),
        "search": id(window.search_box),
        "progress": id(window.progress_bar),
    }

    window.resize(1920, 1080)
    application.processEvents()
    assert window.property("densityMode") == "compact"
    assert not window.future_folder_region.isVisible()
    assert window.open_button.isVisible()
    assert window.transcribe_button.isVisible()
    assert window.candidate_splitter.orientation() == Qt.Orientation.Vertical

    window.resize(2560, 1440)
    application.processEvents()
    splitter_sizes = window.video_workspace.primary_splitter.sizes()
    sidebar_width = window.sidebar.width()
    assert window.property("densityMode") == "expanded"
    assert SIDEBAR_EXPANDED_MIN <= sidebar_width <= SIDEBAR_EXPANDED_MAX
    assert sidebar_width <= window.width() * 0.14
    assert window.header.height() <= HEADER_EXPANDED_HEIGHT
    assert splitter_sizes[0] / sum(splitter_sizes) >= 0.60
    assert window.future_folder_region.isVisible()
    assert window.candidate_splitter.orientation() == Qt.Orientation.Horizontal

    window.resize(3840, 2160)
    application.processEvents()
    assert window.sidebar.width() <= SIDEBAR_EXPANDED_MAX
    assert window.header.height() <= HEADER_EXPANDED_HEIGHT
    assert identities == {
        "video": id(window.video_workspace.video_output),
        "transcript": id(window.transcript_panel),
        "candidates": id(window.candidate_list),
        "search": id(window.search_box),
        "progress": id(window.progress_bar),
    }
    assert window.transcript_panel.toPlainText().endswith("Exact searchable line")
    assert window.candidate_list.count() == 1
    assert window.search_box.text() == "searchable"
    assert window.progress_bar.value() == 37
    window.close()


def test_future_capacity_is_non_interactive_and_domain_free(
    application: QApplication,
) -> None:
    window = SpotlightWindow()
    future_regions = (
        window.future_profile_region,
        window.future_notification_region,
        window.future_folder_region,
        window.future_process_action_region,
        window.future_processing_queue_region,
        window.future_publishing_region,
    )

    for region in future_regions:
        assert region.property("futureFeature") is True
        assert region.focusPolicy() == Qt.FocusPolicy.NoFocus
        assert region.findChildren(QPushButton) == []
        assert region.accessibleName()
    window.close()


def test_existing_workflow_controls_remain_accessible_and_distinct(
    application: QApplication,
) -> None:
    window = SpotlightWindow()

    for control in (
        window.new_project_button,
        window.open_project_button,
        window.open_button,
        window.transcribe_button,
        window.analyze_clips_button,
        window.video_workspace.play_pause_button,
        window.video_workspace.timeline,
        window.search_box,
        window.transcript_panel,
        window.candidate_list,
        window.candidate_details,
    ):
        assert control.accessibleName()
        assert control.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert window.open_button is not window.transcribe_button
    assert window.transcribe_button is not window.analyze_clips_button
    assert window.new_project_button.nextInFocusChain() is window.open_project_button
    assert window.search_box.nextInFocusChain() is window.previous_match_button
    window.close()


def test_transcript_and_candidate_content_is_preserved_by_presentation(
    application: QApplication,
) -> None:
    window = SpotlightWindow()
    segments = (
        TranscriptSegment(1.25, 3.5, "Exact transcript & dialogue"),
        TranscriptSegment(4.0, 8.0, "Exact transcript & dialogue"),
    )
    candidate = make_candidate()

    window._show_transcript(segments)
    window._show_clip_candidates((candidate,))

    transcript = window.transcript_panel.toPlainText()
    details = window.candidate_details.toPlainText()
    assert "Exact transcript & dialogue" in transcript
    assert transcript.count("Exact transcript & dialogue") == 2
    for value in (
        candidate.clip_type,
        str(candidate.score),
        candidate.summary,
        candidate.selection_reasoning,
        *candidate.strong_signals,
        *candidate.weaknesses,
    ):
        assert value in details
    window.close()


def test_responsive_presentation_updates_within_ui_target(
    application: QApplication,
) -> None:
    window = SpotlightWindow()
    window.show()
    application.processEvents()
    latencies_ms: list[float] = []

    for width in (1920, 2560) * 10:
        started = time.perf_counter()
        window.resize(width, 1080 if width == 1920 else 1440)
        application.processEvents()
        latencies_ms.append((time.perf_counter() - started) * 1000)

    p95_ms = sorted(latencies_ms)[int(len(latencies_ms) * 0.95) - 1]
    assert p95_ms < 100
    assert window.motion.active_animation_count == 0
    window.close()
