import json
import urllib.error
import urllib.request
from unittest.mock import patch

import pytest

from spotlight.clip_detection import (
    OLLAMA_ENDPOINT,
    OLLAMA_RESPONSE_SCHEMA,
    OLLAMA_TAGS_ENDPOINT,
    OLLAMA_VERSION_ENDPOINT,
    VIRAL_SIGNAL_WEIGHTS,
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
    clip_type: str = "story setup and payoff",
    signals: tuple[str, ...] = ("story setup and payoff",),
    weaknesses: tuple[str, ...] = (),
    evidence_quotes: tuple[str, ...] | None = None,
) -> RawClipCandidate:
    return RawClipCandidate(
        start_segment=start,
        end_segment=end,
        clip_type=clip_type,
        score=score,
        strong_signals=signals,
        weaknesses=weaknesses,
        evidence_quotes=evidence_quotes or (f"segment {start}",),
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


def test_environment_configures_smaller_batches_and_request_timeout() -> None:
    with patch.dict(
        "spotlight.clip_detection.os.environ",
        {
            "BEEP_OLLAMA_BATCH_CHARACTER_LIMIT": "2500",
            "BEEP_OLLAMA_REQUEST_TIMEOUT_SECONDS": "900",
        },
        clear=True,
    ):
        config = ClipAnalysisConfig.from_environment()

    assert config.batch_character_limit == 2500
    assert config.request_timeout_seconds == 900


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
        "evidence_quotes": ["A joke lands."],
    }
    invalid = {**valid, "score": 101}

    parsed = parse_raw_candidates(json.dumps({"candidates": [valid, invalid]}))

    assert len(parsed) == 1
    assert parsed[0].score == 91


def test_candidate_parser_rejects_malformed_json() -> None:
    with pytest.raises(ClipAnalysisError, match="invalid JSON"):
        parse_raw_candidates("not-json")


def test_ollama_schema_allows_only_grounded_fixed_vocabulary_output() -> None:
    candidate_schema = OLLAMA_RESPONSE_SCHEMA["properties"]["candidates"]["items"]

    assert candidate_schema["additionalProperties"] is False
    assert "summary" not in candidate_schema["properties"]
    assert "selection_reasoning" not in candidate_schema["properties"]
    assert "evidence_quotes" in candidate_schema["required"]


def test_normalization_derives_timestamps_and_moves_visual_claims() -> None:
    segments = [make_segment(index) for index in range(4)]
    batch = build_transcript_batches(segments)[0]
    raw = make_raw(
        1,
        2,
        clip_type="humor",
        signals=("humor", "facial reaction"),
        evidence_quotes=("segment 1",),
    )

    candidate = normalize_candidate(raw, segments, batch)

    assert candidate is not None
    assert candidate.start_seconds == 5.0
    assert candidate.end_seconds == 14.0
    assert candidate.strong_signals == ("humor",)
    assert candidate.clip_type == "humor"
    assert "Visual context is unavailable." in candidate.weaknesses
    assert candidate.summary == 'Transcript evidence: "segment 1"'
    assert candidate.selection_reasoning == (
        "Selected for transcript-supported signals: humor."
    )


def test_normalization_rejects_candidate_without_exact_transcript_evidence() -> None:
    segments = [make_segment(index) for index in range(3)]
    batch = build_transcript_batches(segments)[0]

    candidate = normalize_candidate(
        make_raw(0, 1, evidence_quotes=("Something never said",)), segments, batch
    )

    assert candidate is None


def test_normalization_rejects_generic_dialogue_without_viral_signal() -> None:
    segments = [make_segment(0, "We kept talking about the same thing.")]
    batch = build_transcript_batches(segments)[0]

    candidate = normalize_candidate(
        make_raw(
            0,
            0,
            signals=("ordinary dialogue",),
            evidence_quotes=(segments[0].text,),
        ),
        segments,
        batch,
    )

    assert candidate is None


def test_ranking_vocabulary_covers_approved_viral_signals() -> None:
    assert set(VIRAL_SIGNAL_WEIGHTS) == {
        "humor",
        "laughter",
        "excitement",
        "screaming",
        "surprise",
        "emotional reaction",
        "argument",
        "memorable quote",
        "unexpected event",
        "impressive gameplay",
        "failure",
        "clutch moment",
        "community moment",
        "story setup and payoff",
    }


def test_viral_ranking_beats_high_confidence_low_value_dialogue() -> None:
    segments = [
        make_segment(0, "I cannot believe we won that at the last second!"),
        make_segment(1, "Okay, I guess we can keep talking about the same thing."),
    ]
    batch = build_transcript_batches(segments)[0]
    clutch = normalize_candidate(
        make_raw(
            0,
            0,
            score=70,
            clip_type="clutch moment",
            signals=("clutch moment", "excitement"),
            evidence_quotes=(segments[0].text,),
        ),
        segments,
        batch,
    )
    filler = normalize_candidate(
        make_raw(
            1,
            1,
            score=99,
            clip_type="memorable quote",
            signals=("memorable quote",),
            weaknesses=("Low-energy dialogue.", "Filler."),
            evidence_quotes=(segments[1].text,),
        ),
        segments,
        batch,
    )

    assert clutch is not None
    assert filler is not None
    assert clutch.score > filler.score


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
    assert ranked[0].score == 71
    assert not any("Missing context" in item for item in ranked[0].weaknesses)


def test_unrecovered_batch_boundary_is_marked_and_down_ranked() -> None:
    segments = [make_segment(index, "x" * 40) for index in range(5)]
    batch = build_transcript_batches(
        segments,
        character_limit=90,
        overlap_segments=1,
    )[0]
    raw = make_raw(
        batch.segments[0].index,
        batch.segments[-1].index,
        score=80,
        evidence_quotes=(segments[batch.segments[0].index].text,),
    )

    candidate = normalize_candidate(raw, segments, batch)

    assert candidate is not None
    assert candidate.score == 49
    assert "Missing setup or payoff context." in candidate.weaknesses


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


def test_later_batch_timeout_preserves_validated_partial_candidates() -> None:
    segments = [make_segment(index) for index in range(6)]
    calls = 0
    progress_messages: list[str] = []

    def local_analyzer(batch: object) -> list[RawClipCandidate]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ClipAnalysisError("Ollama /api/generate timed out")
        if calls == 1:
            return [make_raw(0, 0)]
        return []

    result = analyze_transcript(
        segments,
        lambda _value, message: progress_messages.append(message),
        config=ClipAnalysisConfig(batch_character_limit=80, batch_overlap_segments=1),
        analyze_batch=local_analyzer,
    )

    assert len(result.candidates) == 1
    assert result.batch_failures == (
        "Batch 2 of 5 failed: Ollama /api/generate timed out",
    )
    assert any("Batch 2 of 5 failed" in message for message in progress_messages)


class FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.body).encode()


def valid_generate_content() -> str:
    return json.dumps(
        {
            "candidates": [
                {
                    "start_segment": 0,
                    "end_segment": 0,
                    "clip_type": "funny dialogue",
                    "score": 80,
                    "summary": "A joke.",
                    "selection_reasoning": "It stands alone.",
                    "strong_signals": ["humor"],
                    "weaknesses": [],
                    "evidence_quotes": ["segment 0"],
                }
            ]
        }
    )


def test_health_check_detects_ollama_version_and_configured_model() -> None:
    requested_urls: list[str] = []

    def fake_urlopen(request: urllib.request.Request, timeout: int) -> FakeResponse:
        requested_urls.append(request.full_url)
        assert timeout == 10
        if request.full_url == OLLAMA_VERSION_ENDPOINT:
            return FakeResponse({"version": "0.32.5"})
        return FakeResponse({"models": [{"name": "qwen2.5:7b"}]})

    with patch("spotlight.clip_detection.urllib.request.urlopen", fake_urlopen):
        status = OllamaClient(ClipAnalysisConfig()).check_health()

    assert status.version == "0.32.5"
    assert status.models == ("qwen2.5:7b",)
    assert requested_urls == [OLLAMA_VERSION_ENDPOINT, OLLAMA_TAGS_ENDPOINT]


def test_health_check_reports_models_when_configured_model_is_missing() -> None:
    def fake_urlopen(request: urllib.request.Request, timeout: int) -> FakeResponse:
        assert timeout == 10
        if request.full_url == OLLAMA_VERSION_ENDPOINT:
            return FakeResponse({"version": "0.32.5"})
        return FakeResponse({"models": [{"model": "llama3.2:3b"}]})

    with (
        patch("spotlight.clip_detection.urllib.request.urlopen", fake_urlopen),
        pytest.raises(ClipAnalysisError, match="Detected models: llama3.2:3b"),
    ):
        OllamaClient(ClipAnalysisConfig()).check_health()


def test_ollama_adapter_uses_generate_with_0325_response_shape() -> None:
    batch = build_transcript_batches([make_segment(0)])[0]
    captured_payloads: list[dict[str, object]] = []

    def fake_urlopen(request: urllib.request.Request, timeout: int) -> FakeResponse:
        if request.full_url == OLLAMA_VERSION_ENDPOINT:
            return FakeResponse({"version": "0.32.5"})
        if request.full_url == OLLAMA_TAGS_ENDPOINT:
            return FakeResponse({"models": [{"name": "qwen2.5:7b"}]})
        assert request.full_url == OLLAMA_ENDPOINT
        assert timeout == 600
        request_data = request.data
        assert isinstance(request_data, bytes)
        captured_payloads.append(json.loads(request_data.decode("utf-8")))
        return FakeResponse(
            {
                "model": "qwen2.5:7b",
                "response": valid_generate_content(),
                "done": True,
            }
        )

    with patch("spotlight.clip_detection.urllib.request.urlopen", fake_urlopen):
        candidates = OllamaClient(ClipAnalysisConfig()).analyze_batch(batch)

    assert len(candidates) == 1
    assert captured_payloads[0]["model"] == "qwen2.5:7b"
    assert captured_payloads[0]["stream"] is False
    assert "prompt" in captured_payloads[0]
    assert "system" in captured_payloads[0]
    assert "messages" not in captured_payloads[0]


def test_ollama_adapter_displays_real_connection_error() -> None:
    failure = urllib.error.URLError("[WinError 10061] Connection refused")

    with (
        patch("spotlight.clip_detection.urllib.request.urlopen", side_effect=failure),
        pytest.raises(ClipAnalysisError) as captured,
    ):
        OllamaClient(ClipAnalysisConfig()).check_health()

    message = str(captured.value)
    assert OLLAMA_VERSION_ENDPOINT in message
    assert "[WinError 10061] Connection refused" in message
    assert "not running" not in message
