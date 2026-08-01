# Architecture Risks

## Scope and classification

This review treats the modular monolith in `docs/decisions/ADR-0001-modular-monolith.md` as the correct deployment architecture for a local Windows application. Recommendations introduce internal seams, not services or speculative plugin frameworks. Every item is labeled **Verified**, **Assumption**, or **Future risk**.

## Module and responsibility map

| Module | Current responsibility | Assessment |
|---|---|---|
| `src/spotlight/app.py` | Qt composition, dialogs, state, worker adapters, orchestration, persistence calls, formatting, search/navigation | **High — Verified:** 1,185 lines; `SpotlightWindow` spans about 890 lines and is the primary scaling limit. |
| `src/spotlight/clip_detection.py` | Ollama HTTP transport, prompt/schema, batching, output validation, boundary recovery, deduplication/ranking | **High — Verified:** cohesive for MVP, but transport and domain policy must separate before a second provider or streaming. |
| `src/spotlight/projects.py` | SQLite schema, migrations, serialization, project queries | **Medium — Verified:** a useful repository boundary; schema and operational durability need evolution. |
| `src/spotlight/transcription.py` | CUDA DLL discovery, compute choice, FFmpeg extraction, faster-whisper execution | **Medium — Verified:** appropriately isolated, but model lifecycle, cancellation, and diagnostics are mixed. |
| `src/spotlight/media.py` | ffprobe invocation and parsing | **Low — Verified:** small and focused. |
| `src/spotlight/theme.py` | Global Qt stylesheet | **Low — Verified:** isolated, but tokens and accessibility states are not formalized. |

## Current architecture findings

### High — UI/controller concentration (Verified)

`SpotlightWindow.__init__` creates all widgets and mutable state. The same class launches jobs (`open_video`, `start_transcription`, `start_clip_analysis`), changes control availability, persists results (`display_video_metadata`, `display_transcript`, `display_clip_analysis_result`), formats domain data, implements search, and restores projects. Control-reset logic is repeated across success and error slots.

This is not duplicate code in the copy/paste sense; it is redundant state-transition knowledge. Adding playback, a timeline, downloads, publishing jobs, and account switching here would create an implicit state machine spread across callbacks.

**Recommendation:** before the next workflow-heavy feature, specify a small `ProcessingCoordinator` (or equivalent application service) that owns operation identity and transitions, plus typed immutable state delivered to the window. Do not introduce a broad framework. First move one vertical slice—probe/transcribe/analyze—behind it, then stop.

### High — terminal worker behavior is not guaranteed (Verified)

`ProbeTask.run`, `TranscriptionTask.run`, and `ClipAnalysisTask.run` emit a terminal signal only for named domain exceptions or success. Unexpected exceptions, temporary-file creation failures, path races, and defects in callbacks can leave the window in its disabled processing state. `open_video` also calls `Path.stat()` on the UI thread without handling a file disappearing after selection.

There is no cancellation token, global deadline, operation ID, close-event policy, or stale-result rejection. Disabling project switching prevents the common cross-project race, but it is not a general lifecycle contract.

**Recommendation:** one OpenSpec change should require every job to emit exactly one typed terminal outcome, restore UI state in one place, ignore outcomes whose operation/project ID is no longer active, and support cooperative cancellation plus subprocess termination. Include close-window and file-disappears tests.

### Medium — generic and inconsistent diagnostics (Verified)

The media and Ollama paths preserve useful stderr/HTTP details, which is good. Other paths are inconsistent:

- `detect_compute_config` silently converts `ImportError` or `RuntimeError` into CPU fallback without recording the reason.
- `transcribe_audio` wraps any remaining exception as `Transcription failed: ...` but no application logger is configured.
- `_request_json` logs Ollama failures, but no handler or support-log location exists.
- A JSON HTTP error body that is not an object reaches `parsed_detail.get(...)` and can raise an unhandled `AttributeError`.
- Long errors are placed in `progress_label`, which is not configured as a detailed, copyable diagnostic view.

**Recommendation:** add stable error codes, a short user action, and a copyable technical detail. Configure a bounded redacted local log only after defining retention and privacy. Never hide the original exception from support diagnostics.

### Medium — persistence invariants depend on the UI (Verified)

`SpotlightWindow.start_transcription` clears current candidates before replacing a transcript, but `ProjectRepository.replace_transcript` does not clear or version candidates. `replace_candidates` does not verify candidate segment indices against the saved transcript. A future caller can therefore create a logically stale but database-valid candidate set.

**Recommendation:** move derived-data invalidation and referential validation into a repository transaction or, preferably, version transcripts/analysis runs and bind candidates to the analysis input version.

### Medium — synchronous UI-thread database access (Verified)

All repository calls are currently small and local, so keeping them synchronous was a reasonable Version 1 decision. `load_project` uses `fetchall` for the full transcript and candidate set; UI slots perform complete delete/insert replacements. This becomes a responsiveness risk with long histories, thumbnails, publishing jobs, and analytics.

**Trigger:** if any measured UI-thread database operation exceeds 50 ms p95, move it to the bounded job layer. Do not create a general worker system before that measurement.

### Medium — process-global mutable CUDA registration (Verified)

`configure_packaged_cuda_dlls` mutates `_CUDA_DLL_DIRECTORY_HANDLES` and `_CUDA_DLL_DIRECTORIES` without a lock. The current UI launches at most one transcription, so this is safe under current behavior. It becomes a race if parallel jobs or eager background checks are added.

**Recommendation:** initialize the runtime once before accepting transcription jobs, or guard it with a lock. Maintain one GPU workload at a time on 8 GB hardware.

## Provider and platform seams

### AI inference provider boundary

**Verified:** `OllamaClient` is concrete and `analyze_transcript` defaults directly to its `analyze_batch` method. The module also owns the ranking prompt and normalization. Ollama is correctly the sole approved runtime today.

**Future risk — High:** adding a second provider by branching inside `clip_detection.py` would entangle transport, provider capabilities, prompt versioning, streaming, privacy, and ranking policy.

**Safe sequence:** keep Ollama concrete now. When a second provider is approved, extract a narrow typed protocol around health/model discovery and batch/stream generation. Keep transcript batching, candidate schema validation, timestamp derivation, and ranking provider-independent. Each provider must declare locality, cancellation, structured-output, context, and streaming capabilities. Remote providers require a separate privacy/security OpenSpec change; they must not silently reuse local defaults.

### Social platform adapter boundary

**Future risk — High:** no social code exists, which is appropriate. Direct platform conditionals in the window or database would make account isolation, retries, and platform policy untestable.

Before the first destination, define a bundled adapter contract for:

- authorization initiation/callback and token refresh through a credential reference;
- capability discovery (media limits, captions, thumbnails, scheduling, privacy);
- deterministic validation before upload;
- idempotent upload/publish calls and resumable/retry classification;
- typed provider IDs, external post IDs, and normalized status;
- rate-limit metadata and actionable errors;
- no UI objects and no direct SQLite access.

Do not load arbitrary third-party Python plugins in the first commercial release. Bundled, signed adapters keep the attack surface and compatibility matrix manageable. Add dynamic plugins only through a separate trust/sandbox/update proposal.

## Duplication and complexity review

- **Verified, Medium:** UI enable/disable/reset decisions repeat in `display_video_metadata`, `display_probe_error`, `display_transcript`, `display_transcription_error`, `display_cuda_runtime_error`, `display_clip_analysis_result`, and `display_clip_analysis_error`. Consolidate only as part of the job-state change.
- **Verified, Medium:** recent project item display is assembled independently in `OpenProjectDialog.__init__` and `SpotlightWindow.refresh_recent_projects`. A shared small presenter is justified when the item gains more fields.
- **Verified, Low:** transcript and candidate presentation helpers (`_show_transcript`, `_show_clip_candidates`) already avoid larger duplication.
- **Verified, Medium:** `merge_and_rank_candidates` scans the growing merged list for each candidate, giving quadratic worst-case behavior. It is acceptable for small result sets; benchmark and index by interval/type before result counts grow.
- **Verified, Low:** `ProjectRepository` repeats transaction/error wrapping intentionally. A generic repository abstraction would reduce lines but obscure operation-specific errors; do not refactor solely for deduplication.

## Refactoring triggers

| Trigger | Refactor before adding |
|---|---|
| A fourth long-running operation or one-click workflow | Typed job coordinator, operation IDs, cancellation, centralized state transitions |
| Playback/timeline widgets | Split main window into project, source, transcript, candidate, and status view components |
| Second VOD per project or automatic ingest | `content_assets`/`vods` table and stable processing-run identities |
| Approval/rejection capture | Stable candidate IDs and append-only feedback events |
| First connected account | Windows credential-vault boundary and account/domain schema |
| First publishing destination | Bundled platform adapter contract and durable idempotent job queue |
| Second AI runtime | Narrow AI provider protocol and provider capability declaration |
| Any DB call over 50 ms p95 on UI thread | Single-writer background persistence service and paged reads |
| First installer beta | Runtime resource discovery abstraction; remove assumptions tied to `.venv` layout |
| Automatic updates | Signed artifact/manifest verification and rollback architecture |

## Architecture decisions to add later

Each should be its own reviewed ADR/OpenSpec-sized change, not one speculative rewrite:

1. Job lifecycle, cancellation, and UI state ownership.
2. Content asset and processing-run identity model.
3. SQLite concurrency, backup, migration, and recovery policy.
4. Windows credential storage and OAuth callback model.
5. Bundled social-platform adapter contract.
6. Packaging/freezing and prerequisite/model distribution policy.
7. Code signing and automatic-update trust model.
8. Feedback event and learning-data provenance model.

The modular monolith remains the recommended architecture. None of the reviewed evidence justifies microservices or a remote backend for current local processing.
