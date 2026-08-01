# Database Roadmap

## Current SQLite assessment

SQLite remains the right database for a single-user, local Windows modular monolith. Nothing in the stated roadmap requires a server database unless future requirements add multi-device synchronization, concurrent remote users, or a cloud service. The goal should be a disciplined SQLite operating model, not premature replacement.

### Verified schema v1

`ProjectRepository._create_schema_v1` creates:

- `projects`, containing project identity, optional brand name, one VOD path, video metadata, and timestamps;
- `transcript_segments`, ordered by `(project_id, segment_index)`;
- `clip_candidates`, ordered/identified by `(project_id, rank)`, including strong signals and weaknesses as JSON text;
- foreign keys with cascade deletion and basic CHECK constraints;
- recent-project, transcript-order, and candidate-rank indexes;
- schema version in `PRAGMA user_version` and an empty future migration registry.

Repository methods open a connection per operation, enable foreign keys, use parameterized SQL and transaction context managers, and atomically replace transcript/candidate sets. Media is represented only by a path.

## Findings

### High — current identity model cannot support future provenance (Verified)

`projects.id` is stable, but a project embeds one source and has no content-asset/VOD identity. Transcript rows have only a positional key, and candidate identity is its current rank. Rank changes after reanalysis; it cannot safely anchor approvals, edits, exports, posts, analytics, or learning.

**Recommendation:** before feedback, exports, or automatic ingest, migrate to stable UUIDs for content assets, processing/analysis runs, transcripts, and candidates. Keep display rank as mutable data, not identity.

### High — operational durability is underspecified (Verified)

`_connect` sets only `foreign_keys`. There is no busy timeout, explicit journal/synchronous policy, integrity check, backup API, migration backup, corruption recovery, or single-writer coordination. Errors are surfaced but recovery guidance is not.

**Recommendation:** one resilience change should define and test connection pragmas, lock behavior, backup-before-migration, integrity checks, recovery UX, and data-path permissions. Decide WAL only after packaging/backup behavior is tested; account for `-wal`/`-shm` files.

### High — cross-entity invariants are not enforced (Verified)

`replace_transcript` can leave prior candidates in the database when called outside the current UI sequence. `replace_candidates` does not validate segment indices against the stored transcript. Candidate/transcript provenance is implicit.

**Recommendation:** bind candidates to an immutable analysis/transcript version. Replacing a transcript either creates a new run or invalidates dependent candidates in the same transaction.

### Medium — full replacement and full materialization will eventually scale poorly (Verified)

`load_project` fetches all transcript/candidate rows; replacement deletes and reinserts every row. This is appropriate for current sizes but not for extensive histories, analytics, publishing jobs, or many VODs.

**Trigger:** retain simple operations until p95 goals fail. Add paging to project lists/history and incremental run records before adding mutable row-by-row transcript editing.

### Medium — migration framework is structurally present but unproven (Verified)

`FUTURE_MIGRATIONS` and `_apply_future_migrations` enforce contiguous versions, but there is no migration, backup, resume/recovery, or downgrade test. DDL transaction behavior needs explicit tests before schema v2.

### Low — JSON lists are acceptable at current scope (Verified)

Signals and weaknesses as JSON text match the approved change. They are displayed as opaque ordered values and are not queried. Normalize them only if future analytics needs item-level querying; premature child tables would add complexity.

## Target data boundaries

### Store in SQLite

- identities, relationships, paths, hashes/fingerprints, metadata, timestamps, state machines, model/prompt versions, validation results, user decisions, job attempts, external provider IDs, analytics summaries, and opaque credential references;
- small text such as transcripts, titles/descriptions when approved, candidate explanations, caption cues, and error summaries subject to retention policy.

### Never store as database blobs by default

- VODs, extracted WAV, rendered clips, thumbnails, model weights, provider upload chunks, installer packages, or large logs.

Store managed paths plus size, hash, ownership, lifecycle status, and cleanup policy. Original source media is always external/immutable.

### Never store in SQLite

- OAuth access/refresh tokens, provider client secrets, signing keys, updater private keys, passwords, session cookies, or recovery codes. Store only an opaque Windows-vault reference.

## Incremental schema roadmap

Names are illustrative; every version requires a reviewed OpenSpec design and migration test.

### Schema v2 — durable content and run identities

- Add `content_assets`/`vods` with stable ID, project ID, source type, external/source ID, path, normalized path or fingerprint, media metadata, availability, and timestamps.
- Move current project video fields without copying media.
- Add `transcription_runs` with model/device/settings/status/timing and `transcript_segments` tied to a run.
- Add `analysis_runs` with provider/model/prompt/schema/batch settings/status/timing.
- Give `clip_candidates` stable IDs and `analysis_run_id`; keep rank as a column.
- Preserve exactly one migrated current asset/run per existing project.

This change is a prerequisite for multiple VODs, reanalysis history, approvals, exports, analytics, and learning.

### Schema v3 — export and feedback provenance

- Add append-only `candidate_feedback` with candidate ID, decision, reason/tags if approved, actor/local policy, timestamp, and supersession rather than destructive overwrite.
- Add `boundary_edits` or versioned candidate revisions.
- Add `exports` with asset/candidate revision, render recipe/version, output path/hash/size/status/timing; no media blob.
- Define cleanup/missing-output behavior.

### Schema v4 — creators, profiles, and account metadata

- Add `profiles` with stable ID, display/brand settings, timestamps; migrate optional project brand metadata deliberately rather than equating brand text with a profile.
- Add `profile_projects` or a project `profile_id` according to ownership rules.
- Add `connected_accounts` with provider, immutable external account ID, display metadata, scopes/status/expiry, and opaque `credential_ref` only.
- Add `profile_source_accounts` and `profile_destinations` link tables with uniqueness and explicit role constraints.
- Support shared destinations through relationships, never token duplication.

### Schema v5 — durable automation and publishing

- Add `jobs` with type, state, idempotency key, payload version/reference, attempts, next attempt, lease/heartbeat if needed, error code/detail, created/updated timestamps.
- Add Twitch discovery cursors and source VOD external IDs with uniqueness for deduplication.
- Add `publish_attempts`/`published_items` with destination connection, export, provider request/external IDs, normalized status, schedule, timestamps, and response metadata without secrets.
- Keep a single local writer and explicit restart recovery.

### Schema v6 — analytics and learning

- Add provider analytics snapshots keyed by published item, metric, provider timestamp/window, and ingestion cursor/version.
- Add feature/label provenance for learning: candidate/input versions, prompt/model/ranker versions, user decision, edit/export/publish/outcome links.
- Add retention and compaction policies; raw provider payloads should be avoided or bounded/redacted.
- Keep model artifacts outside SQLite and version them by path/hash.

## SQLite operating model

1. **Single writer:** route writes through one application persistence service once background jobs arrive. Readers may use short-lived read connections.
2. **Short transactions:** never hold a transaction during FFmpeg, AI, network, user dialog, or file copy work.
3. **Busy behavior:** configure a bounded busy timeout and show an actionable lock error after it expires; never spin indefinitely.
4. **Journal policy:** benchmark DELETE versus WAL under antivirus, crash, backup, installer, and network/removable-path constraints. Keep DB in local app data, not a sync folder.
5. **Backups:** use SQLite's backup API to a versioned local backup before migration and on a documented cadence; verify integrity and restore.
6. **Migrations:** one-way, contiguous, idempotence-aware, transactional where SQLite permits, with preflight disk space and app-version compatibility. Never silently downgrade.
7. **Integrity:** run lightweight startup/version checks; perform full integrity checks during maintenance/recovery, not every launch if they miss startup targets.
8. **Observability:** measure operation name, row counts, duration, result/error code, and DB size without transcript/path/account content.
9. **Pagination:** recent remains 10; page complete project/history/job/analytics views as volume grows.
10. **Timestamps:** store UTC instants plus explicit schedule time zone/offset semantics where user intent matters.

## Scalability goals

- 10,000 projects remain listable through indexed pagination without loading all rows.
- A project with 10,000 transcript segments and 200 candidates loads in ≤250 ms p95 on reference SSD; UI blocking ≤50 ms.
- Recent-project query and startup schema/version check each complete in ≤50 ms p95.
- Transcript replace ≤250 ms p95; candidate replace ≤100 ms p95 for reference sizes.
- A publishing queue of 100,000 historical jobs remains queryable by state/profile/destination through indexed pages.
- Database growth is predictable and visible; maintenance warns before disk exhaustion.

These are proposed goals requiring a benchmark harness; they are not current measurements.

## Migration release checklist

- [ ] Migration has explicit old/new schema, invariants, row-count mapping, and expected disk growth.
- [ ] Pre-migration integrity and free-space checks pass.
- [ ] Restorable backup is created and verified before mutation.
- [ ] Success, interrupted/failing migration, corrupt input, locked file, disk full, and unsupported-newer-version tests pass.
- [ ] Exact Unicode transcript/candidate/path data and timestamps round-trip.
- [ ] Original media and vault credentials are untouched.
- [ ] Old app behavior after migration is explicitly blocked or supported; no accidental downgrade.
- [ ] Performance targets pass at small and large data volumes.
- [ ] Privacy/retention/export/delete behavior is documented for new data.
