## 1. Local analysis foundation

- [x] 1.1 Add typed clip-candidate, raw model-response, and analysis-result models with validation boundaries for required fields and the 0–100 score range.
- [x] 1.2 Add local analysis configuration for the Ollama loopback endpoint, selected model name, transcript input budget, and batch overlap without storing machine-specific settings in Git or adding another AI SDK/runtime.
- [x] 1.3 Implement clear diagnostics for unavailable Ollama, a missing configured model, request failure, and unusable structured output.
- [x] 1.4 Document free Windows installation, model download, local-only behavior, and verification commands for the chosen small Ollama model.

## 2. Transcript preparation and inference

- [x] 2.1 Implement deterministic serialization of ordered transcript segments with stable indices and exact timestamps.
- [x] 2.2 Implement bounded transcript batching with segment overlap and tests for empty, short, long, and boundary-spanning transcripts.
- [x] 2.3 Define the schema-constrained local prompt and scoring rubric covering every approved positive signal, negative signal, standalone-context preference, and visual-evidence limitation.
- [x] 2.4 Implement the narrow Ollama adapter and parse its structured candidate responses without accepting model-generated timestamps.
- [x] 2.5 Add adapter tests using local test doubles for successful output, runtime/model failures, malformed JSON, missing fields, out-of-range scores, and operation with Ollama as the only AI runtime.

## 3. Candidate normalization and ranking

- [x] 3.1 Convert valid model segment ranges into source-derived start and end timestamps and reject missing, reversed, or out-of-range references.
- [x] 3.2 Combine candidates from all batches, merge compatible adjacent-batch setup/payoff ranges, sort deterministically by score, and deduplicate materially overlapping candidates while retaining the stronger result.
- [x] 3.3 Ensure visual-only concepts are never recorded as detected signals and are retained only as weaknesses or missing context when relevant.
- [x] 3.4 Add focused tests for timestamp preservation, ranking order, overlap resolution, setup and payoff split across adjacent batches, unrecoverable missing-context down-ranking, mixed positive/negative evidence, and partial rejection of invalid candidates.

## 4. In-memory result lifecycle

- [x] 4.1 Store the current validated ranked candidate set in application memory without adding or changing SQLite tables.
- [x] 4.2 Replace current in-memory candidates only after a complete successful analysis and preserve the current list when a retry fails.
- [x] 4.3 Add tests proving candidates are session-only, are not written to SQLite, and can be regenerated from the completed transcript after restart.

## 5. Responsive application workflow

- [x] 5.1 Add an analysis coordinator that requires a completed transcript, runs one local analysis at a time, and leaves transcript segments immutable.
- [x] 5.2 Run analysis through the existing Qt background-task pattern with progress, success, and failure signals delivered safely to the UI thread.
- [x] 5.3 Add workflow tests proving analysis eligibility, retry behavior, transcript preservation, and failure recovery without replacing current in-memory results.

## 6. Minimal candidate review UI

- [x] 6.1 Add an `Analyze Clips` control that is enabled only for a completed non-empty transcript and disabled while analysis is active.
- [x] 6.2 Add a theme-consistent ranked candidate list showing score, clip type, timestamps, and short summary without adding playback or editing controls.
- [x] 6.3 Add a candidate detail view showing selection rationale, strong signals, weaknesses, and missing context, including the transcript-only visual limitation.
- [x] 6.4 Clear session-only candidates when the active project changes and keep the UI actionable after local runtime or analysis errors.
- [x] 6.5 Add focused UI tests for control eligibility, progress/failure states, descending result order, selection details, and long-list scrolling.

## 7. Verification and documentation

- [x] 7.1 Run pytest, Ruff lint, Ruff formatting check, and Pyright and resolve every failure before committing implementation.
- [x] 7.2 Manually verify a representative transcript with humor/setup-payoff and a low-value transcript, confirming explanations and missing visual context are honest.
- [x] 7.3 Verify no transcript, prompt payload, model file, media, local configuration, or secret is tracked by Git and no candidate persistence schema was introduced.
- [x] 7.4 Update user and architecture documentation to describe the approved local clip-analysis workflow, limitations, model setup, and recovery steps.
