## Context

See `proposal.md` for motivation and `specs/clip-candidate-ranking/spec.md` for the behavior contract. BEEP currently owns timestamped transcript segments in memory after faster-whisper completes, while its long-running work already uses Qt background tasks. The first clip-detection version must fit the existing modular monolith, run on one Windows PC, preserve transcript data, and produce dependable structured results from VOD-length input that may exceed a local model's context window.

Visual frames are not part of the input in this version. The design therefore cannot verify facial reactions, menus, loading screens, or other visual-only events.

## Goals / Non-Goals

**Goals:**

- Introduce a small analysis boundary that accepts immutable timestamped segments and returns validated clip candidates.
- Keep inference local and off the PySide6 UI thread.
- Handle long transcripts with bounded batches and deterministic result normalization.
- Make ranking explainable and retain explicit weaknesses or missing context.
- Keep complete, validated analysis results in memory for the current application session.
- Use Ollama as the sole AI inference runtime.

**Non-Goals:**

- Frame sampling, facial-reaction detection, menu/loading-screen recognition, or other computer vision.
- Editing, rendering, playback, captions, exports, posting, or automatic selection of a final clip.
- Cloud inference, remote telemetry, model training, or personalization.
- A second AI SDK/runtime, candidate database tables, or candidate restoration after restart.
- Continuous background analysis, multiple concurrent analyses, or a generalized job queue.
- Perfect score calibration across creators or game genres in the first version.

## Decisions

### Use Ollama as the local inference runtime behind one narrow adapter

The analyzer will call an Ollama model through its loopback API and request schema-constrained JSON. Ollama is the sole AI inference runtime for Version 1: the application will not integrate a remote AI provider or a second AI SDK/runtime. Configuration will name one documented small instruct model and allow the Ollama model name to be changed without altering ranking logic. Startup or analysis errors will distinguish a missing Ollama runtime, a missing model, and invalid model output.

Ollama matches the project's local-only direction, keeps model lifecycle outside the Python process, and avoids adding a large inference stack to the UI application. A direct Python transformer integration was rejected for the first version because it would duplicate model download, GPU/CPU selection, memory management, and serving concerns already handled by a local runtime. Rule-only scoring was rejected because it would be too brittle for humor, setup/payoff, awkwardness, and roleplay context.

### Analyze bounded, overlapping transcript batches

The application will serialize ordered transcript segments with stable segment indices and exact timestamps. It will build batches to a configured input budget and retain a segment overlap between adjacent batches so setup/payoff near a boundary can be visible in both. The model will return source segment-index ranges rather than inventing raw timestamps; BEEP will derive timestamps from those source segments.

Candidates touching a batch edge will retain an explicit incomplete-context weakness unless an overlapping candidate from the adjacent batch supplies the missing setup or payoff. Normalization may merge compatible adjacent-batch candidates into one source segment range, preserving the necessary setup through payoff. If the complete narrative cannot be recovered, the candidate remains down-ranked or explicitly marked as incomplete rather than being presented as self-contained.

Sending the entire transcript in one request was rejected because long VODs can exceed context limits and make failures expensive. Fixed wall-clock chunks were rejected because dialogue density varies and could waste context or split dense exchanges unpredictably.

### Separate model judgment from deterministic validation and ranking cleanup

The local model will suggest clip type, raw score, summary, rationale, positive signals, and weaknesses. Application code will validate the JSON schema, confirm referenced segment indices, derive bounded timestamps, clamp neither missing fields nor invalid scores, sort valid results, and deduplicate materially overlapping candidates. Invalid candidates will be discarded individually; a response with no valid candidates will be treated as an analysis failure rather than silently presented as success.

This preserves the model's semantic judgment while keeping structural correctness deterministic and testable. Trusting model timestamps and arbitrary JSON was rejected because malformed local output could create misleading or unusable candidates.

### Use one explicit scoring rubric in the prompt

The prompt will define the 0–100 scale and list the approved positive and negative signals. It will require evidence tied to the supplied transcript, favor standalone comprehension, and require weaknesses when context is missing. Visual-only concepts will be described as unavailable, with an instruction never to claim they were observed.

Multiple specialized scoring passes were rejected for the first version because they multiply inference time and reconciliation complexity. One structured pass per batch plus deterministic aggregation is the smallest useful design.

### Keep Version 1 candidate results in memory

The coordinator will own the current validated candidate list in memory and replace it only after a successful complete analysis. A failed retry will leave the current in-memory list intact. Closing the application discards candidate results; users can run analysis again from the persisted transcript.

Candidate database tables and restart restoration are deliberately deferred to a separate future OpenSpec change. This keeps Version 1 focused on inference quality, ranking, and review behavior before establishing a durable schema for results that may evolve.

### Add a minimal ranked-results region to the existing window

After transcription, an `Analyze Clips` control starts one analysis task. The UI will show processing status, then a score-ordered list with a compact summary. Selecting a candidate will show all required explanation fields. The transcript remains unchanged and available. No playback or editing action will be attached to candidates.

A separate multi-page workflow was rejected because the first version needs only one additional review surface and should preserve the small desktop layout.

### Reuse the existing Qt background-task pattern

Analysis orchestration and local API calls will execute away from the UI thread and report success, failure, and coarse progress through Qt signals. Only one analysis may run at a time. This follows the existing responsiveness pattern without introducing a worker service or persistent queue.

## Risks / Trade-offs

- **[Transcript-only input misses visual humor and visual low-value sections]** → Label visual context as unavailable in candidate weaknesses and prohibit claims that visual signals were detected; defer visual analysis to a separate proposal.
- **[Local model scores can vary between runs]** → Use deterministic sampling settings where supported, a fixed rubric, schema-constrained output, and deterministic sorting/deduplication; store the model name with results.
- **[Overlapping batches can produce duplicate candidates]** → Compare source segment ranges and retain the higher-scoring materially overlapping candidate.
- **[Batch boundaries can separate long setup/payoff sequences]** → Overlap adjacent batches, merge compatible boundary candidates, and down-rank or mark missing context when the complete setup/payoff cannot be recovered.
- **[Long VOD analysis can be slow on an 8 GB GPU or CPU fallback]** → Use a documented small quantized model, bounded requests, one active analysis, progress messaging, and an explicit retry path.
- **[Model output may be malformed or unsupported by an installed Ollama version]** → Validate every response, surface actionable runtime/model errors, and never replace current in-memory results until a complete candidate set is valid.
- **[In-memory candidates are lost at application shutdown]** → Make the session-only lifecycle explicit and allow users to rerun analysis from the completed transcript; address persistence in a separate change.
- **[A single general model may under-rank creator-specific humor]** → Keep the first rubric transparent and defer creator profiles or feedback learning until real results justify added scope.

## Migration Plan

1. Add Ollama-only local runtime/model configuration and startup diagnostics without changing existing transcription behavior.
2. Ship analysis disabled until a completed transcript is present and keep results in memory only.
3. If the feature must be rolled back, remove or hide the analysis UI and local adapter; no data migration or candidate-table cleanup is required.
