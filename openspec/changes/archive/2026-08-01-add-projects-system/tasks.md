## 1. Persistence foundation

- [x] 1.1 Add Windows per-user application-data path resolution for the SQLite database without placing machine-specific paths in source control.
- [x] 1.2 Add explicit SQLite connection initialization with foreign keys and transactional creation of schema version 1 for new databases.
- [x] 1.3 Add an ordered migration registry for future schema versions without implementing legacy conversion or rollback logic when no earlier database format exists.
- [x] 1.4 Add initialization tests covering a new database, repeated initialization, foreign-key enforcement, schema-version recording, and safe rejection of unsupported newer versions.

## 2. Project data access

- [x] 2.1 Add typed project summary and immutable complete project snapshot models for identity, brand text, VOD metadata, transcript segments, and ranked candidates.
- [x] 2.2 Implement project creation with stable IDs, non-empty-name validation, optional brand text, timestamps, and support for duplicate display names.
- [x] 2.3 Implement recent-project listing limited to 10 projects, ordered by last-opened and updated time with deterministic tie-breaking.
- [x] 2.4 Implement complete project loading with ordered transcript and candidates, validating strong signals and weaknesses decoded from JSON text columns, plus actionable storage errors.
- [x] 2.5 Add isolated SQLite tests proving multiple projects remain independent and complete snapshots round-trip exact text, timestamps, metadata, candidate fields, JSON list ordering, and Unicode Windows paths.

## 3. Transactional workflow persistence

- [x] 3.1 Persist successful VOD path and metadata updates for the active project and atomically clear transcript and candidates when the source VOD changes.
- [x] 3.2 Atomically replace an active project's transcript only after complete successful transcription, retaining the prior complete transcript on failure.
- [x] 3.3 Atomically replace a saved active project's candidates only after complete successful analysis, retaining prior durable candidates on storage failure and keeping results without a saved owner in memory only.
- [x] 3.4 Add workflow tests for completion-boundary saves, failed replacements, source changes, exact transcript preservation, saved-project restoration, unsaved-project session behavior, and candidate persistence without changing ranking behavior.

## 4. Project lifecycle coordination

- [x] 4.1 Require an active project before accepting new project-owned VOD state and expose clear no-active-project state to the UI.
- [x] 4.2 Load and validate one complete snapshot before replacing the active project, leaving the prior active state unchanged when restoration fails.
- [x] 4.3 Restore saved metadata, transcript search state inputs, and ranked candidate display inputs after restart without rerunning ffprobe, transcription, or Ollama.
- [x] 4.4 Detect an inaccessible saved source path, restore review data, mark the media unavailable, and disable only actions that require the original VOD.
- [x] 4.5 Add coordinator tests for create/open transitions, restart restoration, failed loads, missing media, and switching between projects.

## 5. Minimal Projects UI

- [x] 5.1 Add a theme-consistent Projects section to the existing sidebar with New Project, Open Project, active-project text, and a list of at most 10 recent projects.
- [x] 5.2 Add a small New Project dialog for required project name and optional project-specific Brand name with visible blank-name validation and no reusable-profile behavior.
- [x] 5.3 Add a local Open Project selection dialog using stored project summaries and useful distinguishing metadata rather than a filesystem picker.
- [x] 5.4 Connect recent-project selection and project dialogs to the lifecycle coordinator while preserving current video, transcript, search, and clip-analysis UI behavior.
- [x] 5.5 Add focused UI tests for empty state, active-project display, the 10-project recent limit and ordering, validation, successful switching, failed restoration, and missing-source action state.

## 6. Scope, recovery, and documentation

- [x] 6.1 Verify the schema contains paths and structured Version 1 data only, stores candidate signal and weakness lists in JSON text columns, and contains no media blobs or tables for exports, titles, descriptions, thumbnails, publishing, profiles, Twitch, editing, or posting.
- [x] 6.2 Document project creation, reopening, database location, local-only storage, missing-media behavior, backup expectations, the project-specific meaning of Brand name, and Version 1 limitations.
- [x] 6.3 Verify no database, media, transcript, candidate payload, model, export, secret, cache, temporary file, or machine-specific configuration is tracked by Git.
- [x] 6.4 Manually verify creating two projects, restarting BEEP without automatic reopening, restoring each project's data, and opening a project whose source VOD was moved without offering relinking.
- [x] 6.5 Verify project rename, deletion, duplication, search, pinning, missing-media relinking, automatic reopening, reusable profiles, Twitch importing, editing, exports, posting, thumbnails, titles, and descriptions were not added.

## 7. Validation and delivery

- [x] 7.1 Run pytest and resolve every failure.
- [x] 7.2 Run Ruff lint and Ruff formatting check and resolve every failure.
- [x] 7.3 Run Pyright and resolve every error.
- [x] 7.4 Review the final diff against the OpenSpec requirements and confirm no deferred feature or unrelated dependency was added before committing.
