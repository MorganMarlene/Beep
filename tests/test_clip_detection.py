import json
import urllib.error
from unittest.mock import patch

import pytest

from spotlight.clip_detection import (
    OLLAMA_ENDPOINT,
    ClipAnalysisConfig,
    ClipAnalysisError,
    OllamaClient,
    RawClipCandidate,
    analyze_transcript,
    build_transcript_batches,
    merge_and_rank_candidates,
    normalize_candidate,
    parse_raw_candidates,
    serialize_batch,
)
from spotlight.transcription import TranscriptSegment


def make_segment(index: int, text: str | None = None) -> TranscriptSegment:
    return TranscriptSegment(
        start_seconds=float(index * 5),
        end_seconds=float(index * 5 + 4),
        text=text or f"segment {index}",
    )


def make_raw(
    start: int,
    end: int,
    *,
    score: int = 80,
    clip_type: str = "story payoff",
    signals: tuple[str, ...] = ("setup and payoff",),
    weaknesses: tuple[str, ...] = (),
) -> RawClipCandidate:
    return RawClipCandidate(
        start_segment=start,
        end_segment=end,
        clip_type=clip_type,
        score=score,
        summary="A concise summary",
        selection_reasoning="The setup makes the payoff understandable.",
        strong_signals=signals,
        weaknesses=weaknesses,
    )


def test_batches_are_bounded_ordered_and_overlap() -> None:
    segments = [make_segment(index, "x" * 30) for index in range(6)]

    batches = build_transcript_batches(
        segments,
        character_limit=100,
        overlap_segments=1,
    )

    assert len(batches) > 1
    assert batches[0].segments[-1].index == batches[1].segments[0].index
    assert all(
        len(serialize_batch(batch)) <= 100 or len(batch.segments) == 1
        for batch in batches
    )
    assert [item.index for item in batches[0].segments] == sorted(
        item.index for item in batches[0].segments
    )


def test_empty_transcript_has_no_batches() -> None:
    assert build_transcript_batches([]) == []


def test_candidate_parser_keeps_valid_items_and_rejects_invalid_items() -> None:
    valid = {
        "start_segment": 0,
        "end_segment": 2,
        "clip_type": "deadpan humor",
        "score": 91,
        "summary": "A joke lands.",
        "selection_reasoning": "Clear setup and payoff.",
        "strong_signals": ["deadpan humor"],
        "weaknesses": [],
    }
    invalid = {**valid, "score": 101}

    parsed = parse_raw_candidates(json.dumps({"candidates": [valid, invalid]}))

    assert len(parsed) == 1
    assert parsed[0].score == 91


def test_candidate_parser_rejects_malformed_json() -> None:
    with pytest.raises(ClipAnalysisError, match="invalid JSON"):
        parse_raw_candidates("not-json")


def test_normalization_derives_timestamps_and_moves_visual_claims() -> None:
    segments = [make_segment(index) for index in range(4)]
    batch = build_transcript_batches(segments)[0]
    raw = make_raw(
        1,
        2,
        signals=("funny dialogue", "facial reaction"),
    )

    candidate = normalize_candidate(raw, segments, batch)

    assert candidate is not None
    assert candidate.start_seconds == 5.0
    assert candidate.end_seconds == 14.0
    assert candidate.strong_signals == ("funny dialogue",)
    assert "Unverified visual context: facial reaction" in candidate.weaknesses


def test_normalization_rejects_model_range_outside_batch() -> None:
    segments = [make_segment(index, "x" * 40) for index in range(5)]
    first_batch = build_transcript_batches(
        segments,
        character_limit=90,
        overlap_segments=1,
    )[0]

    assert normalize_candidate(make_raw(0, 4), segments, first_batch) is None


def test_adjacent_batch_candidates_merge_setup_through_payoff() -> None:
    segments = [make_segment(index) for index in range(8)]
    batches = build_transcript_batches(
        segments,
        character_limit=105,
        overlap_segments=2,
    )
    first = normalize_candidate(make_raw(0, 2, score=82), segments, batches[0])
    second = normalize_candidate(make_raw(1, 3, score=90), segments, batches[1])

    assert first is not None
    assert second is not None
    ranked = merge_and_rank_candidates([first, second], segments)

    assert len(ranked) == 1
    assert ranked[0].start_segment == 0
    assert ranked[0].end_segment == 3
    assert ranked[0].start_seconds == segments[0].start_seconds
    assert ranked[0].end_seconds == segments[3].end_seconds
    assert ranked[0].score == 90
    assert not any("Missing context" in item for item in ranked[0].weaknesses)


def test_unrecovered_batch_boundary_is_marked_and_down_ranked() -> None:
    segments = [make_segment(index, "x" * 40) for index in range(5)]
    batch = build_transcript_batches(
        segments,
        character_limit=90,
        overlap_segments=1,
    )[0]
    raw = make_raw(batch.segments[0].index, batch.segments[-1].index, score=80)

    candidate = normalize_candidate(raw, segments, batch)

    assert candidate is not None
    assert candidate.score == 70
    assert any("Missing context" in weakness for weakness in candidate.weaknesses)


def test_analysis_is_in_memory_and_repeatable_with_a_local_test_double() -> None:
    segments = [make_segment(index) for index in range(3)]
    progress_updates: list[int] = []

    def local_analyzer(_batch: object) -> list[RawClipCandidate]:
        return [make_raw(0, 2)]

    first = analyze_transcript(
        segments,
        lambda value, _message: progress_updates.append(value),
        analyze_batch=local_analyzer,
    )
    second = analyze_transcript(
        segments,
        lambda _value, _message: None,
        analyze_batch=local_analyzer,
    )

    assert first.candidates == second.candidates
    assert progress_updates[-1] == 100


class FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.body).encode()


def test_ollama_adapter_uses_only_the_fixed_loopback_endpoint() -> None:
    segments = [make_segment(0)]
    batch = build_transcript_batches(segments)[0]
    response_content = json.dumps(
        {
            "candidates": [
                {
                    "start_segment": 0,
                    "end_segment": 0,
                    "clip_type": "funny dialogue",
                    "score": 80,
                    "summary": "A joke.",
                    "selection_reasoning": "It stands alone.",
                    "strong_signals": ["funny dialogue"],
                    "weaknesses": [],
                }
            ]
        }
    )
    captured_urls: list[str] = []

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured_urls.append(request.full_url)  # type: ignore[attr-defined]
        assert timeout == 180
        return FakeResponse({"message": {"content": response_content}})

    with patch("spotlight.clip_detection.urllib.request.urlopen", fake_urlopen):
        candidates = OllamaClient(ClipAnalysisConfig()).analyze_batch(batch)

    assert len(candidates) == 1
    assert captured_urls == [OLLAMA_ENDPOINT]


def test_ollama_adapter_reports_local_runtime_failure() -> None:
    batch = build_transcript_batches([make_segment(0)])[0]
    failure = urllib.error.URLError("connection refused")

    with (
        patch("spotlight.clip_detection.urllib.request.urlopen", side_effect=failure),
        pytest.raises(ClipAnalysisError, match="not running locally"),
    ):
        OllamaClient(ClipAnalysisConfig()).analyze_batch(batch)
