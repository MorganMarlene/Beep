from spotlight.app import find_matching_segment_indices, navigate_match
from spotlight.transcription import TranscriptSegment


def make_segment(text: str) -> TranscriptSegment:
    return TranscriptSegment(start_seconds=1.25, end_seconds=2.5, text=text)


def test_search_is_case_insensitive_and_returns_every_matching_segment() -> None:
    segments = [
        make_segment("A Brilliant PLAY"),
        make_segment("A quiet moment"),
        make_segment("Another brilliant finish"),
    ]

    assert find_matching_segment_indices(segments, "brilliant") == [0, 2]
    assert find_matching_segment_indices(segments, "PLAY") == [0]


def test_empty_search_has_no_matches() -> None:
    assert find_matching_segment_indices([make_segment("Keep this text")], "") == []


def test_search_does_not_change_segment_content() -> None:
    segment = make_segment("  Exact transcript text.  ")

    find_matching_segment_indices([segment], "transcript")

    assert segment.start_seconds == 1.25
    assert segment.end_seconds == 2.5
    assert segment.text == "  Exact transcript text.  "


def test_match_navigation_wraps_forward_and_backward() -> None:
    matches = [1, 4, 8]

    assert navigate_match(matches, None, 1) == 1
    assert navigate_match(matches, 1, 1) == 4
    assert navigate_match(matches, 8, 1) == 1
    assert navigate_match(matches, None, -1) == 8
    assert navigate_match(matches, 1, -1) == 8


def test_match_navigation_handles_no_matches() -> None:
    assert navigate_match([], None, 1) is None
