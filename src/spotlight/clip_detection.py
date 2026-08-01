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
MISSING_CONTEXT_PENALTY = 10
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
    summary: str
    selection_reasoning: str
    strong_signals: tuple[str, ...]
    weaknesses: tuple[str, ...]


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
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_segment": {"type": "integer"},
                    "end_segment": {"type": "integer"},
                    "clip_type": {"type": "string"},
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "summary": {"type": "string"},
                    "selection_reasoning": {"type": "string"},
                    "strong_signals": {"type": "array", "items": {"type": "string"}},
                    "weaknesses": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "start_segment",
                    "end_segment",
                    "clip_type",
                    "score",
                    "summary",
                    "selection_reasoning",
                    "strong_signals",
                    "weaknesses",
                ],
            },
        }
    },
    "required": ["candidates"],
}


SYSTEM_PROMPT = """You rank potential short-form clips from timestamped
transcript segments. Return only candidates supported by the supplied transcript.
Scores range from 0 to
100. Prioritize funny dialogue, deadpan humor, arguments, awkward moments,
unexpected roleplay, complete story setup and payoff, and moments understandable
outside GTA RP. Down-rank music-only passages, repetitive crafting, long dead air,
driving without meaningful dialogue, and action without humor or understandable
context. Use source segment indices, never invented timestamps. Include necessary
setup through payoff. If context is incomplete, lower the score and state what is
missing. Transcript analysis cannot detect facial reactions, menus, loading screens,
or other visual-only evidence: never list those as detected strong signals; mention
them only as unverified or missing visual context. Keep summaries and explanations
short and concrete."""


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
                    summary=_require_text(item.get("summary"), "summary"),
                    selection_reasoning=_require_text(
                        item.get("selection_reasoning"), "selection_reasoning"
                    ),
                    strong_signals=_require_text_list(
                        item.get("strong_signals"), "strong_signals"
                    ),
                    weaknesses=_require_text_list(item.get("weaknesses"), "weaknesses"),
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
            updated_weaknesses.append(f"Unverified visual context: {signal}")
        else:
            accepted.append(signal)
    return tuple(dict.fromkeys(accepted)), tuple(dict.fromkeys(updated_weaknesses))


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

    signals, weaknesses = _sanitize_visual_signals(raw.strong_signals, raw.weaknesses)
    boundary_limited = (
        batch.has_previous and raw.start_segment == batch.segments[0].index
    ) or (batch.has_next and raw.end_segment == batch.segments[-1].index)
    score = raw.score
    if boundary_limited:
        weakness = "Missing context: candidate touches an analysis batch boundary."
        weaknesses = tuple(dict.fromkeys((*weaknesses, weakness)))
        score = max(0, score - MISSING_CONTEXT_PENALTY)

    return ClipCandidate(
        start_segment=raw.start_segment,
        end_segment=raw.end_segment,
        start_seconds=start.start_seconds,
        end_seconds=end.end_seconds,
        clip_type=raw.clip_type,
        score=score,
        summary=raw.summary,
        selection_reasoning=raw.selection_reasoning,
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
            item
            for item in weaknesses
            if "analysis batch boundary" not in item.casefold()
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
