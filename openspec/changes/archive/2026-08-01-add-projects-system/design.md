## Context

See `proposal.md` for motivation and `specs/project-management/spec.md` for the behavior contract. BEEP is a single-user Windows desktop modular monolith. The current window owns one active VOD workflow; transcripts can be reconstructed after transcription, while AI clip candidates currently exist only in memory. The existing UI already has a sidebar and uses Qt background tasks for slow media and inference work.

This change introduces durable project identity and a significant SQLite schema. Original media, generated media, models, and other large files must remain outside both the database and Git. Project loading must not partially replace the visible active state.

## Goals / Non-Goals

**Goals:**

- Define one durable aggregate for project identity, VOD metadata, transcript segments, and clip candidates.
- Support multiple projects and deterministic restoration after process restart.
- Keep database access explicit, transactional, testable, and compatible with Windows application-data paths.
- Integrate project selection into the current window without creating a multi-page framework.
- Preserve the existing transcript and candidate models at the persistence boundary.

**Non-Goals:**

- Portable project bundles, database-file selection, cloud sync, multi-user access, or concurrent application instances.
- Copying, moving, deleting, relinking, or managing original media.
- Reusable creator profiles or brand configuration; Version 1 stores only an optional brand name as metadata on one project.
- Storage or workflows for exports, titles, descriptions, thumbnails, publishing, Twitch, editing, or posting.
- Project rename, deletion, duplication, search, pinning, missing-media relinking, or automatic reopening.
- A general repository framework, ORM, event bus, autosave scheduler, or background job system.

## Decisions

### Create schema version 1 in one application-owned SQLite database

BEEP will keep one database in its per-user application-data directory. A small persistence module will enable foreign keys, create schema version 1 transactionally for a new database, and record the schema version. No earlier BEEP database format exists, so Version 1 will not contain speculative legacy conversion or rollback logic. The initialization boundary will retain an ordered migration registry so future approved schema versions can add tested forward migrations.

A separate database file per project was rejected because it would require file discovery, recent-file bookkeeping, and cross-file migration handling. An ORM was rejected because the schema and queries are small and explicit SQL gives clearer transaction and migration behavior.

### Model projects as stable identities with normalized child rows

The conceptual schema is:

```text
projects
- id
- name
- brand_name (nullable)
- source_path (nullable until a VOD is loaded)
- filename and probed/file metadata (nullable)
- created_at
- updated_at
- last_opened_at

transcript_segments
- project_id
- segment_index
- start_seconds
- end_seconds
- text

clip_candidates
- project_id
- rank
- start_seconds
- end_seconds
- start_segment
- end_segment
- clip_type
- score
- summary
- selection_reasoning
- strong_signals_json
- weaknesses_json
```

Stable generated project IDs allow duplicate display names. Ordered child keys preserve transcript order and candidate rank. Strong signals and weaknesses are encoded as JSON arrays in required text columns and decoded through a validated persistence boundary, preserving list order without separate child tables. Storing the entire application state as one serialized blob was rejected because it weakens validation and migration safety; JSON is limited to the two naturally list-valued candidate fields.

Version 1 deliberately omits columns and tables for exported clips, generated copy, thumbnails, publishing, reusable profiles, or other future concepts. Future changes will add those only when their behavior is approved.

### Save complete processing results transactionally

Successful metadata probing updates the active project's VOD fields in one transaction. A completed transcript replaces all transcript rows for that project in one transaction. A completed clip-analysis result replaces all candidate rows for that project in one transaction. Failed or incomplete work does not erase the last complete stored result. If candidate persistence fails, the completed result remains available in memory for the current session while the prior durable result remains unchanged.

Incremental per-segment commits were rejected because interruption could expose a partial transcript as complete. Generic continuous autosave was rejected because the current state changes at clear workflow completion boundaries.

When a new VOD replaces the active project's source, BEEP will clear the stored transcript and candidates in the same metadata transaction so derived data can never appear to belong to the wrong media.

### Load into an immutable snapshot before changing active UI state

The persistence boundary will return a complete typed project snapshot containing project data and ordered child records. The coordinator validates the snapshot before replacing the active in-memory state and updating widgets. If loading fails, the prior active project remains untouched.

Direct widget-by-widget database hydration was rejected because a mid-load error could leave mixed state from two projects. Exposing live database row objects was rejected because it couples UI state to connection lifetime and SQL details.

### Treat source-path availability separately from persisted review data

Opening a project does not re-probe or rewrite its saved data automatically. BEEP checks whether the stored source path is currently accessible. If not, it restores metadata, transcript, and candidates for review while disabling operations that need the original VOD and showing an unavailable-source status.

Discarding the project when media is missing was rejected because transcripts and candidate judgments remain useful and the user may restore the file later. Automatic path searching was rejected because it can be slow, ambiguous, and outside Version 1.

### Add a compact Projects section to the existing sidebar

The sidebar will gain New Project and Open Project actions, a list limited to the 10 most recent projects, and active-project text. Open Project uses an application dialog backed by stored project summaries, not a filesystem picker. Recent ordering uses `last_opened_at` then `updated_at`, with stable ID as a deterministic tie-breaker.

A full project dashboard or new navigation framework was rejected because Version 1 needs only project selection and identity. Project rename, deletion, duplication, search, pinning, missing-media relinking, and automatic reopening remain unapproved.

### Keep database work synchronous unless measurement shows it blocks

The expected project queries are small local SQLite operations and may run synchronously at workflow boundaries. Existing FFmpeg, transcription, and Ollama operations remain off the UI thread. Database transactions will be short and will never include media probing or inference.

A database worker and queue were rejected because they add lifecycle and coordination complexity without evidence that these bounded local queries threaten responsiveness. If measured project loads become perceptible, moving snapshot loading to the existing Qt task pattern can be a focused follow-up without changing the persistence contract.

## Risks / Trade-offs

- **[A future build encounters an unsupported schema version]** → Record schema version 1, reject unknown newer versions without destructive recovery, and retain an ordered migration boundary for future approved upgrades.
- **[A VOD is moved or removed]** → Restore review data, report source unavailability, and disable only media-dependent actions.
- **[A crash occurs during transcript or candidate replacement]** → Use one transaction per complete replacement so SQLite retains either the old complete state or the new complete state.
- **[Duplicate project names confuse users]** → Preserve stable IDs and show distinguishing metadata such as brand name, VOD filename, or last-opened time in selection lists.
- **[Candidate persistence conflicts with the prior session-only design]** → The `clip-candidate-ranking` delta explicitly supersedes that lifecycle for saved projects while retaining memory-only behavior for results without a saved owner.
- **[Malformed JSON loses candidate explanation lists]** → Encode only arrays of strings, validate decoded values on load, and fail the complete snapshot load without partially changing active UI state.
- **[The schema anticipates speculative future fields]** → Do not add tables or columns for exports, generated copy, thumbnails, publishing, profiles, or posting in Version 1.
- **[SQLite access briefly blocks the UI]** → Keep queries bounded and transactions short; measure before introducing background database infrastructure.

## Migration Plan

1. Add application-data database path resolution, connection initialization, foreign-key enforcement, and schema-version handling.
2. Create schema version 1 transactionally for a new database and establish an empty ordered migration registry for future versions; do not implement legacy conversion or rollback logic.
3. Introduce typed project summaries and complete project snapshots, then verify create, save, list, and load behavior independently of the UI.
4. Require an active project for new VOD state and connect successful metadata, transcription, and candidate completion boundaries to transactional saves.
5. Add the compact sidebar controls and restoration flow after persistence behavior is covered by tests.
6. If initialization fails, leave the database file untouched, report the error, and do not attempt destructive repair.
