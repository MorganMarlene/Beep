"""Local transcript analysis for explainable clip candidates."""

import json
import logging
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from spotlight.transcription import TranscriptSegment

ProgressCallback = Callable[[int, str], None]
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_VERSION_ENDPOINT = f"{OLLAMA_BASE_URL}/api/version"
OLLAMA_TAGS_ENDPOINT = f"{OLLAMA_BASE_URL}/api/tags"
OLLAMA_ENDPOINT = f"{OLLAMA_BASE_URL}/api/generate"
DEFAULT_BATCH_CHARACTER_LIMIT = 12_000
DEFAULT_BATCH_OVERLAP_SEGMENTS = 8
MISSING_CONTEXT_PENALTY = 15
VIRAL_SIGNAL_WEIGHTS = {
    "humor": 28,
    "laughter": 24,
    "excitement": 20,
    "screaming": 22,
    "surprise": 24,
    "emotional reaction": 20,
    "argument": 22,
    "memorable quote": 24,
    "unexpected event": 26,
    "impressive gameplay": 24,
    "failure": 20,
    "clutch moment": 30,
    "community moment": 22,
    "story setup and payoff": 26,
}
CLIP_TYPES = tuple(VIRAL_SIGNAL_WEIGHTS)
LOW_VALUE_PENALTIES = {
    "Missing setup or payoff context.": 15,
    "Visual context is unavailable.": 5,
    "A menu or loading screen cannot be verified from the transcript.": 10,
    "Music-only section.": 35,
    "Silence or dead air.": 35,
    "Repetitive conversation.": 22,
    "Low-energy dialogue.": 22,
    "Filler.": 25,
    "Gameplay context is unclear from the transcript.": 12,
}
WEAKNESS_LABELS = tuple(LOW_VALUE_PENALTIES)
VISUAL_ONLY_TERMS = (
    "facial reaction",
    "face reaction",
    "loading screen",
    "menu",
    "visual reaction",
)
LOGGER = logging.getLogger(__name__)


class ClipAnalysisError(Exception):
    """Raised when local clip analysis cannot produce usable candidates."""


@dataclass(frozen=True, slots=True)
class ClipAnalysisConfig:
    """Local Ollama and transcript batching settings."""

    model_name: str = DEFAULT_OLLAMA_MODEL
    batch_character_limit: int = DEFAULT_BATCH_CHARACTER_LIMIT
    batch_overlap_segments: int = DEFAULT_BATCH_OVERLAP_SEGMENTS

    @classmethod
    def from_environment(cls) -> "ClipAnalysisConfig":
        """Load the model name without allowing a non-local inference endpoint."""
        model_name = os.environ.get("BEEP_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()
        return cls(model_name=model_name or DEFAULT_OLLAMA_MODEL)


@dataclass(frozen=True, slots=True)
class IndexedTranscriptSegment:
    """A transcript segment with its stable source index."""

    index: int
    segment: TranscriptSegment


@dataclass(frozen=True, slots=True)
class TranscriptBatch:
    """One bounded, ordered set of transcript segments sent to Ollama."""

    segments: tuple[IndexedTranscriptSegment, ...]
    has_previous: bool
    has_next: bool


@dataclass(frozen=True, slots=True)
class RawClipCandidate:
    """Structured semantic judgment returned by the local model."""

    start_segment: int
    end_segment: int
    clip_type: str
    score: int
    strong_signals: tuple[str, ...]
    weaknesses: tuple[str, ...]
    evidence_quotes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClipCandidate:
    """A validated candidate with timestamps derived from source segments."""

    start_segment: int
    end_segment: int
    start_seconds: float
    end_seconds: float
    clip_type: str
    score: int
    summary: str
    selection_reasoning: str
    strong_signals: tuple[str, ...]
    weaknesses: tuple[str, ...]
    boundary_limited: bool = False


@dataclass(frozen=True, slots=True)
class ClipAnalysisResult:
    """A complete in-memory candidate set and the Ollama model used."""

    candidates: tuple[ClipCandidate, ...]
    model_name: str


@dataclass(frozen=True, slots=True)
class OllamaStatus:
    """Live local Ollama version and installed model names."""

    version: str
    models: tuple[str, ...]


OLLAMA_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "start_segment": {"type": "integer"},
                    "end_segment": {"type": "integer"},
                    "clip_type": {"type": "string", "enum": list(CLIP_TYPES)},
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "strong_signals": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": list(VIRAL_SIGNAL_WEIGHTS),
                        },
                    },
                    "weaknesses": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(WEAKNESS_LABELS)},
                    },
                    "evidence_quotes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "required": [
                    "start_segment",
                    "end_segment",
                    "clip_type",
                    "score",
                    "strong_signals",
                    "weaknesses",
                    "evidence_quotes",
                ],
            },
        }
    },
    "required": ["candidates"],
}


SYSTEM_PROMPT = """You identify transcript moments with genuine short-form viral
potential. All generated values MUST be in English. The only exception is an
evidence quote, which MUST copy the supplied transcript verbatim and MUST NOT be
translated or paraphrased.

Return candidates only when exact transcript evidence supports at least one allowed
strong signal. Prioritize humor, laughter, excitement, screaming, surprise,
emotional reactions, arguments, memorable quotes, unexpected events, impressive
gameplay, failures, clutch moments, community-worthy moments, and complete story
setup and payoff. A normal exchange of dialogue is not a candidate. Down-rank or
omit menus/loading uncertainty, music-only sections, silence or dead air, repetitive
conversation, low-energy dialogue, and filler.

Do not infer a person, action, event, emotion, gameplay result, or visual occurrence
that the transcript does not explicitly support. Transcript analysis cannot detect
facial reactions, menus, loading screens, or other visual-only evidence. Never claim
that it did. Use only the allowed English enum values in clip_type, strong_signals,
and weaknesses. Supply one or more short evidence_quotes copied exactly from the
selected transcript range for every candidate. Use source segment indices, never
invented timestamps. Include necessary setup through payoff. If context is missing,
use the matching missing-context weakness and lower confidence. Score is model
confidence from 0 to 100; BEEP performs the final ranking deterministically."""


def serialize_segment(indexed: IndexedTranscriptSegment) -> str:
    """Serialize a source segment deterministically for the local model."""
    segment = indexed.segment
    return (
        f"[{indexed.index}] [{segment.start_seconds:.3f}-{segment.end_seconds:.3f}] "
        f"{segment.text}"
    )


def serialize_batch(batch: TranscriptBatch) -> str:
    """Serialize all segments in one transcript batch."""
    return "\n".join(serialize_segment(segment) for segment in batch.segments)


def build_transcript_batches(
    segments: Sequence[TranscriptSegment],
    character_limit: int = DEFAULT_BATCH_CHARACTER_LIMIT,
    overlap_segments: int = DEFAULT_BATCH_OVERLAP_SEGMENTS,
) -> list[TranscriptBatch]:
    """Split a transcript into bounded batches with stable overlapping indices."""
    if character_limit <= 0:
        raise ValueError("character_limit must be positive")
    if overlap_segments < 0:
        raise ValueError("overlap_segments cannot be negative")
    if not segments:
        return []

    indexed = [
        IndexedTranscriptSegment(i, segment) for i, segment in enumerate(segments)
    ]
    ranges: list[tuple[int, int]] = []
    start = 0
    while start < len(indexed):
        end = start
        used = 0
        while end < len(indexed):
            size = len(serialize_segment(indexed[end])) + (1 if end > start else 0)
            if end > start and used + size > character_limit:
                break
            used += size
            end += 1
            if used >= character_limit:
                break
        ranges.append((start, end))
        if end >= len(indexed):
            break
        retained = min(overlap_segments, max(end - start - 1, 0))
        start = end - retained

    return [
        TranscriptBatch(
            segments=tuple(indexed[start:end]),
            has_previous=start > 0,
            has_next=end < len(indexed),
        )
        for start, end in ranges
    ]


def build_user_prompt(batch: TranscriptBatch) -> str:
    """Build the batch prompt, including explicit boundary context."""
    boundary_note = (
        "This batch has earlier transcript context. " if batch.has_previous else ""
    ) + ("This batch has later transcript context. " if batch.has_next else "")
    return (
        f"{boundary_note}Identify only strong clip candidates. If a candidate touches "
        "a batch edge and needs unavailable context, record that weakness and lower "
        f"its score.\n\nTRANSCRIPT:\n{serialize_batch(batch)}"
    )


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value.strip()


def _require_text_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of text values")
    return tuple(item.strip() for item in value if item.strip())


def parse_raw_candidates(content: str) -> list[RawClipCandidate]:
    """Parse model JSON and reject candidates with missing or invalid fields."""
    try:
        document: Any = json.loads(content)
    except json.JSONDecodeError as error:
        raise ClipAnalysisError("Ollama returned invalid JSON.") from error
    if not isinstance(document, dict) or not isinstance(
        document.get("candidates"), list
    ):
        raise ClipAnalysisError("Ollama returned an invalid candidate response.")

    candidates: list[RawClipCandidate] = []
    for item in document["candidates"]:
        try:
            if not isinstance(item, dict):
                raise ValueError("candidate must be an object")
            start = item.get("start_segment")
            end = item.get("end_segment")
            score = item.get("score")
            if not isinstance(start, int) or not isinstance(end, int):
                raise ValueError("segment indices must be integers")
            if (
                not isinstance(score, int)
                or isinstance(score, bool)
                or not 0 <= score <= 100
            ):
                raise ValueError("score must be an integer from 0 through 100")
            candidates.append(
                RawClipCandidate(
                    start_segment=start,
                    end_segment=end,
                    clip_type=_require_text(item.get("clip_type"), "clip_type"),
                    score=score,
                    strong_signals=_require_text_list(
                        item.get("strong_signals"), "strong_signals"
                    ),
                    weaknesses=_require_text_list(item.get("weaknesses"), "weaknesses"),
                    evidence_quotes=_require_text_list(
                        item.get("evidence_quotes"), "evidence_quotes"
                    ),
                )
            )
        except (TypeError, ValueError):
            continue
    return candidates


class OllamaClient:
    """Small loopback-only adapter for Ollama health and generation requests."""

    def __init__(self, config: ClipAnalysisConfig) -> None:
        self.config = config
        self._status: OllamaStatus | None = None

    @staticmethod
    def _request_json(request: urllib.request.Request, timeout: int) -> Any:
        """Run one local request while preserving useful transport diagnostics."""
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raw_detail = error.read().decode("utf-8", errors="replace")
            try:
                parsed_detail: Any = json.loads(raw_detail)
                detail = parsed_detail.get("error", raw_detail)
            except json.JSONDecodeError:
                detail = raw_detail
            message = (
                f"Ollama request to {request.full_url} failed with HTTP "
                f"{error.code}: {detail or error.reason}"
            )
            LOGGER.error(message)
            raise ClipAnalysisError(message) from error
        except urllib.error.URLError as error:
            message = (
                f"Could not connect to Ollama at {request.full_url}: {error.reason!s}"
            )
            LOGGER.error(message, exc_info=True)
            raise ClipAnalysisError(message) from error
        except TimeoutError as error:
            message = f"Ollama request to {request.full_url} timed out: {error}"
            LOGGER.error(message, exc_info=True)
            raise ClipAnalysisError(message) from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            message = f"Ollama returned an unreadable response from {request.full_url}."
            LOGGER.error(message, exc_info=True)
            raise ClipAnalysisError(message) from error

    def check_health(self) -> OllamaStatus:
        """Read local version and model tags, confirming the configured model."""
        version_document = self._request_json(
            urllib.request.Request(OLLAMA_VERSION_ENDPOINT, method="GET"),
            timeout=10,
        )
        tags_document = self._request_json(
            urllib.request.Request(OLLAMA_TAGS_ENDPOINT, method="GET"),
            timeout=10,
        )
        try:
            version = version_document["version"]
            raw_models = tags_document["models"]
            if not isinstance(version, str) or not isinstance(raw_models, list):
                raise TypeError
            models = tuple(
                name
                for item in raw_models
                if isinstance(item, dict)
                for name in (item.get("name") or item.get("model"),)
                if isinstance(name, str)
            )
        except (KeyError, TypeError) as error:
            raise ClipAnalysisError(
                "Ollama returned an invalid response from /api/version or /api/tags."
            ) from error
        status = OllamaStatus(version=version, models=models)
        if self.config.model_name not in status.models:
            detected = ", ".join(status.models) or "none"
            raise ClipAnalysisError(
                f"Ollama {status.version} is running, but model "
                f"'{self.config.model_name}' is not installed. Detected models: "
                f"{detected}. Run 'ollama pull {self.config.model_name}'."
            )
        self._status = status
        return status

    def analyze_batch(self, batch: TranscriptBatch) -> list[RawClipCandidate]:
        """Request candidate judgments for one transcript batch."""
        if self._status is None:
            self.check_health()
        payload = json.dumps(
            {
                "model": self.config.model_name,
                "stream": False,
                "format": OLLAMA_RESPONSE_SCHEMA,
                "options": {"temperature": 0},
                "system": SYSTEM_PROMPT,
                "prompt": build_user_prompt(batch),
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            OLLAMA_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response_body = self._request_json(request, timeout=180)
        try:
            content = response_body["response"]
            done = response_body["done"]
        except (KeyError, TypeError) as error:
            raise ClipAnalysisError(
                "Ollama returned an invalid /api/generate response."
            ) from error
        if not isinstance(content, str) or done is not True:
            raise ClipAnalysisError(
                "Ollama returned an incomplete /api/generate response."
            )
        return parse_raw_candidates(content)


def _sanitize_visual_signals(
    signals: tuple[str, ...], weaknesses: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    accepted: list[str] = []
    updated_weaknesses = list(weaknesses)
    for signal in signals:
        if any(term in signal.casefold() for term in VISUAL_ONLY_TERMS):
            updated_weaknesses.append("Visual context is unavailable.")
        else:
            accepted.append(signal)
    return tuple(dict.fromkeys(accepted)), tuple(dict.fromkeys(updated_weaknesses))


def _canonical_values(
    values: tuple[str, ...], allowed: Sequence[str]
) -> tuple[str, ...]:
    allowed_by_key = {value.casefold(): value for value in allowed}
    canonical = (
        allowed_by_key[value.casefold()]
        for value in values
        if value.casefold() in allowed_by_key
    )
    return tuple(dict.fromkeys(canonical))


def _normalize_for_evidence(value: str) -> str:
    return " ".join(value.casefold().split())


def _supported_evidence_quotes(
    quotes: tuple[str, ...], selected_segments: Sequence[TranscriptSegment]
) -> tuple[str, ...]:
    transcript_text = _normalize_for_evidence(
        " ".join(segment.text for segment in selected_segments)
    )
    supported = (
        quote.strip()
        for quote in quotes
        if len(_normalize_for_evidence(quote)) >= 3
        and _normalize_for_evidence(quote) in transcript_text
    )
    return tuple(dict.fromkeys(supported))


def _grounded_summary(evidence_quotes: tuple[str, ...]) -> str:
    evidence = " / ".join(f'"{quote}"' for quote in evidence_quotes[:2])
    return f"Transcript evidence: {evidence}"


def _selection_reasoning(signals: tuple[str, ...]) -> str:
    return "Selected for transcript-supported signals: " + ", ".join(signals) + "."


def _viral_score(
    model_confidence: int,
    signals: tuple[str, ...],
    weaknesses: tuple[str, ...],
    duration_seconds: float,
) -> int:
    strongest_signal = max(VIRAL_SIGNAL_WEIGHTS[signal] for signal in signals)
    additional_signals = min(18, max(0, len(signals) - 1) * 6)
    duration_adjustment = 5 if 8 <= duration_seconds <= 60 else 0
    if duration_seconds < 3 or duration_seconds > 90:
        duration_adjustment -= 15
    penalties = sum(LOW_VALUE_PENALTIES.get(item, 0) for item in weaknesses)
    score = (
        22
        + strongest_signal
        + additional_signals
        + round(model_confidence * 0.2)
        + duration_adjustment
        - penalties
    )
    return min(100, max(0, score))


def normalize_candidate(
    raw: RawClipCandidate,
    source_segments: Sequence[TranscriptSegment],
    batch: TranscriptBatch,
) -> ClipCandidate | None:
    """Derive timestamps and reject invalid source ranges."""
    if (
        raw.start_segment < 0
        or raw.end_segment < raw.start_segment
        or raw.end_segment >= len(source_segments)
    ):
        return None
    batch_indices = {item.index for item in batch.segments}
    if raw.start_segment not in batch_indices or raw.end_segment not in batch_indices:
        return None
    start = source_segments[raw.start_segment]
    end = source_segments[raw.end_segment]
    if start.start_seconds < 0 or end.end_seconds <= start.start_seconds:
        return None

    clip_types = _canonical_values((raw.clip_type,), CLIP_TYPES)
    raw_signals, raw_weaknesses = _sanitize_visual_signals(
        raw.strong_signals, raw.weaknesses
    )
    signals = _canonical_values(raw_signals, tuple(VIRAL_SIGNAL_WEIGHTS))
    weaknesses = _canonical_values(raw_weaknesses, WEAKNESS_LABELS)
    if not clip_types or not signals:
        return None
    selected_segments = source_segments[raw.start_segment : raw.end_segment + 1]
    evidence_quotes = _supported_evidence_quotes(raw.evidence_quotes, selected_segments)
    if not evidence_quotes:
        return None
    boundary_limited = (
        batch.has_previous and raw.start_segment == batch.segments[0].index
    ) or (batch.has_next and raw.end_segment == batch.segments[-1].index)
    if boundary_limited:
        weakness = "Missing setup or payoff context."
        weaknesses = tuple(dict.fromkeys((*weaknesses, weakness)))
    duration_seconds = end.end_seconds - start.start_seconds
    score = _viral_score(raw.score, signals, weaknesses, duration_seconds)

    return ClipCandidate(
        start_segment=raw.start_segment,
        end_segment=raw.end_segment,
        start_seconds=start.start_seconds,
        end_seconds=end.end_seconds,
        clip_type=max(signals, key=VIRAL_SIGNAL_WEIGHTS.__getitem__),
        score=score,
        summary=_grounded_summary(evidence_quotes),
        selection_reasoning=_selection_reasoning(signals),
        strong_signals=signals,
        weaknesses=weaknesses,
        boundary_limited=boundary_limited,
    )


def _overlap_size(first: ClipCandidate, second: ClipCandidate) -> int:
    return max(
        0,
        min(first.end_segment, second.end_segment)
        - max(first.start_segment, second.start_segment)
        + 1,
    )


def _can_merge(first: ClipCandidate, second: ClipCandidate) -> bool:
    if first.clip_type.casefold() != second.clip_type.casefold():
        return False
    overlap = _overlap_size(first, second)
    shorter = min(
        first.end_segment - first.start_segment + 1,
        second.end_segment - second.start_segment + 1,
    )
    return overlap > 0 and (
        overlap / shorter >= 0.5 or first.boundary_limited or second.boundary_limited
    )


def merge_and_rank_candidates(
    candidates: Sequence[ClipCandidate], source_segments: Sequence[TranscriptSegment]
) -> list[ClipCandidate]:
    """Merge compatible boundary stories, deduplicate, and rank deterministically."""
    merged: list[ClipCandidate] = []
    for candidate in sorted(
        candidates, key=lambda item: (-item.score, item.start_segment)
    ):
        match_index = next(
            (
                index
                for index, current in enumerate(merged)
                if _can_merge(current, candidate)
            ),
            None,
        )
        if match_index is None:
            merged.append(candidate)
            continue
        current = merged[match_index]
        stronger = current if current.score >= candidate.score else candidate
        start_index = min(current.start_segment, candidate.start_segment)
        end_index = max(current.end_segment, candidate.end_segment)
        weaknesses = tuple(dict.fromkeys((*current.weaknesses, *candidate.weaknesses)))
        boundary_limited = False
        weaknesses = tuple(
            item for item in weaknesses if item != "Missing setup or payoff context."
        )
        recovered_score = stronger.score + (
            MISSING_CONTEXT_PENALTY if stronger.boundary_limited else 0
        )
        merged[match_index] = replace(
            stronger,
            start_segment=start_index,
            end_segment=end_index,
            start_seconds=source_segments[start_index].start_seconds,
            end_seconds=source_segments[end_index].end_seconds,
            strong_signals=tuple(
                dict.fromkeys((*current.strong_signals, *candidate.strong_signals))
            ),
            weaknesses=weaknesses,
            score=min(100, recovered_score),
            boundary_limited=boundary_limited,
        )
    return sorted(merged, key=lambda item: (-item.score, item.start_seconds))


def analyze_transcript(
    segments: Sequence[TranscriptSegment],
    progress: ProgressCallback,
    config: ClipAnalysisConfig | None = None,
    analyze_batch: Callable[[TranscriptBatch], list[RawClipCandidate]] | None = None,
) -> ClipAnalysisResult:
    """Analyze a completed transcript locally and return an in-memory result."""
    if not segments:
        raise ClipAnalysisError("A completed transcript is required before analysis.")
    settings = config or ClipAnalysisConfig.from_environment()
    batches = build_transcript_batches(
        segments,
        settings.batch_character_limit,
        settings.batch_overlap_segments,
    )
    analyzer = analyze_batch or OllamaClient(settings).analyze_batch
    normalized: list[ClipCandidate] = []
    for index, batch in enumerate(batches):
        progress(
            int(index / len(batches) * 90),
            f"Analyzing transcript batch {index + 1} of {len(batches)}...",
        )
        for raw in analyzer(batch):
            candidate = normalize_candidate(raw, segments, batch)
            if candidate is not None:
                normalized.append(candidate)

    candidates = merge_and_rank_candidates(normalized, segments)
    if not candidates:
        raise ClipAnalysisError(
            "Ollama did not return any valid clip candidates. Try again or use a "
            "different local Ollama model."
        )
    progress(100, "Clip analysis complete.")
    return ClipAnalysisResult(tuple(candidates), settings.model_name)
