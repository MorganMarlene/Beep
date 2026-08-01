# BEEP Project Health Audit

Audit date: 2026-08-01  
Audited revision: `ce371f9` on `feature/projects-system`  
Scope: repository documentation, OpenSpec artifacts, tracked source and tests, dependency metadata, Git topology, and read-only local runtime diagnostics.

## How to read this audit

- **Verified** means the finding is directly evidenced in the repository or by a named read-only diagnostic.
- **Assumption** means the audit could not prove the condition without production data, hardware benchmarks, platform credentials, or a packaged build.
- **Future risk** means the current MVP is not defective, but the named capability would be unsafe if added without the recommended boundary.
- Severity reflects commercial impact: **Critical** can compromise accounts, updates, or user data; **High** can cause data loss, stuck workflows, or expensive redesign; **Medium** materially affects quality or operations; **Low** is localized improvement.

No verified Critical defect was found in the current local-only MVP. The Critical items below are explicitly future risks that must become release gates before credentials, publishing, or automatic updates exist.

## Executive assessment

BEEP has a sound small-MVP core: media probing, transcription, Ollama analysis, and project persistence are separated into modules; long-running media and AI work uses Qt's thread pool; SQL writes are transactional; paths rather than media are persisted; candidate output is validated before display; and the 61-test suite exercises the most important pure logic and persistence paths.

The architecture is not yet safe to extend directly into the complete commercial roadmap. The main constraint is concentration: `SpotlightWindow` in `src/spotlight/app.py` is a 1,185-line UI/controller/state/persistence coordinator, while `ProjectRepository` models one project as one VOD and `OllamaClient` is a concrete adapter embedded beside ranking policy. Those choices are reasonable for Version 0.1, but the next few changes should establish workflow, storage, and provider seams before playback, automation, multiple accounts, or publishing make those seams expensive to extract.

## Highest-priority findings

| Priority | Severity | Classification | Finding and evidence | Recommended OpenSpec-sized response |
|---:|---|---|---|---|
| 1 | Critical | Future risk | No credential model exists today, which is correct for the MVP. Future Twitch and publishing tokens would be exposed if placed in the current plaintext SQLite database (`ProjectRepository._create_schema_v1`). | Specify a Windows credential-vault boundary, per-connection authorization identity, redaction rules, and OAuth PKCE before the first account-linking change. |
| 2 | Critical | Future risk | No signed update or release trust chain exists. An automatic updater would become a code-execution supply-chain boundary. | Specify code signing, signed manifests, TLS, atomic install/rollback, release channels, and compromised-key response before implementing updates. |
| 3 | High | Verified | `SpotlightWindow` spans lines 231-1121 and owns widget construction, workflow state, worker launch, error recovery, formatting, and persistence calls. | Extract one workflow/application service and small view-model state objects before adding one-click processing or playback; keep Qt widgets in the window. |
| 4 | High | Verified | `ProbeTask.run`, `TranscriptionTask.run`, and `ClipAnalysisTask.run` catch only expected domain exceptions. An unexpected exception emits no terminal signal, so controls disabled by `open_video`, `start_transcription`, or `start_clip_analysis` can remain disabled. There is no cancellation or operation identity. | Add a cancellable job contract with exactly one success/failure/cancel terminal event and a UI state reducer; include close-during-job tests. |
| 5 | High | Verified | Schema v1 embeds a single `source_path` and video metadata row in `projects`; candidates use `(project_id, rank)` as identity. This cannot cleanly represent many VODs, analysis versions, feedback, exports, or durable publishing references. | Introduce stable content-asset, analysis-run, and candidate IDs through one backed-up migration before approvals or automatic ingest. |
| 6 | High | Verified | SQLite uses a new connection per call with foreign keys, but no `busy_timeout`, WAL policy, integrity check, backup-before-migration, recovery path, or writer serialization. Calls are synchronous from UI slots such as `display_transcript` and `display_clip_analysis_result`. | Add database resilience and timing instrumentation; move operations exceeding the UI budget off-thread while preserving a single-writer policy. |
| 7 | High | Verified | Ollama batches are serial and non-streaming (`OllamaClient.analyze_batch`, `analyze_transcript`), each with a 180-second timeout, no cancellation, retry budget, or total deadline. Provider transport and ranking policy share `clip_detection.py`. | First add measurement/cancellation; then a streaming local result protocol; introduce a provider protocol only when another approved runtime is actually added. |
| 8 | High | Verified | There is no Windows executable/installer configuration, application icon/resource manifest, signing pipeline, prerequisite bootstrapper, updater, SBOM, third-party notices, or repository `LICENSE`. Installed PySide6, CUDA/cuDNN, and CTranslate2 directories alone occupy about 2.5 GB in the audit environment. | Run a packaging spike before beta: choose freezer/installer, define prerequisite/model policy, produce license inventory, and test a clean VM. |
| 9 | High | Verified | Tests are strong unit tests but provide no measured coverage, real FFmpeg/faster-whisper/Ollama integration lane, SQLite lock/corruption recovery tests, cancellation/thread-lifecycle tests, packaged-build smoke test, accessibility tests, or clean-machine test. No CI configuration is tracked. | Add a tiered Windows CI and hardware/manual validation matrix before automation or publishing. |
| 10 | High | Verified | Both completed OpenSpec changes remain active, `openspec/specs/` has no canonical specifications, and the projects delta supersedes the earlier memory-only candidate lifecycle only through another active change. `openspec/config.yaml` is empty. README scope also says Ollama is out of scope before later documenting it as present. | Archive/sync completed changes, consolidate canonical specs, add project context and nonfunctional requirement prompts, and reconcile current-scope documentation. |

## Current strengths

- **Verified:** `probe_video`, `transcribe_video`, and `analyze_transcript` run through `QRunnable` tasks rather than on the UI thread.
- **Verified:** `transcribe_video` removes its temporary WAV in a `finally` block; `save_video` clears source-derived rows in the same SQLite transaction when the path changes.
- **Verified:** SQLite foreign keys and CHECK constraints cover basic transcript and candidate validity, and repository operations use parameters rather than interpolating values.
- **Verified:** Ollama is fixed to `127.0.0.1:11434`, model output is parsed and normalized, timestamps come from transcript segments, visual-only claims are moved to weaknesses, and batch-boundary candidates are penalized or merged.
- **Verified:** CUDA preference uses FP16, CPU fallback uses INT8, and NVIDIA Python-package DLL directories are registered for the process on Windows.
- **Verified:** `.gitignore` excludes media, models, databases, transcripts, exports, caches, temporary files, local configuration, and `.venv`.
- **Verified:** OpenSpec changes state explicit exclusions and contain scenario-oriented requirements and checked task plans.

## Severity summary

| Severity | Audit conclusion |
|---|---|
| Critical | No verified current defect. Credential isolation and updater trust are Critical future gates. |
| High | Current concentration, lifecycle, persistence durability, packaging, testing, and OpenSpec governance need work before the related roadmap expands. |
| Medium | Diagnostics, UI-thread database work, memory copies, scaling/accessibility, dependency policy, and edge-case coverage should be addressed at their documented triggers. |
| Low | Focused modules and deliberate MVP simplifications should remain simple until measurements or approved scope justify change. |

Findings overlap across documents, so this audit intentionally avoids presenting an artificial aggregate defect count.

## Release-readiness checklist

The current source checkout is an engineering MVP, not a commercial release candidate.

- [ ] All approved OpenSpec changes are validated, reviewed, archived, and synchronized into canonical specs.
- [ ] `pytest`, Ruff lint, Ruff format check, Pyright, Windows integration tests, and packaged smoke tests pass from a clean checkout.
- [ ] No Critical or High finding remains open without a documented, time-bounded acceptance decision.
- [ ] Upgrade and downgrade behavior is documented; every schema migration is backed up and restore-tested.
- [ ] Crash-safe job state, cancellation, retry boundaries, and user-visible diagnostics are verified.
- [ ] Original media preservation and temporary-file cleanup are verified under failure and cancellation.
- [ ] Privacy, data location, retention, deletion, telemetry, and support-log behavior are documented.
- [ ] Repository license, dependency licenses, FFmpeg build/license choice, SBOM, and third-party notices are reviewed.
- [ ] Executables and installer are signed; release artifacts and update manifests are reproducible and verified.
- [ ] Accessibility, keyboard-only, screen-reader, high-contrast, 1440p, mixed-DPI, and multi-monitor checks pass.
- [ ] Reference-machine startup, database, transcription, AI, memory, disk, and thermal performance goals pass at p95.
- [ ] Clean install, upgrade, repair, uninstall, and user-data preservation pass on supported Windows versions.
- [ ] Account linking and publishing remain disabled until the security gates in `security-and-account-linking.md` pass.

## Audit limitations

- No production VOD corpus, damaged-media corpus, OAuth client, social sandbox account, installer, or updater exists, so quality and platform behavior are future risks rather than verified defects.
- No representative transcription or AI benchmark was run because the repository has no benchmark fixture or approved media. Goals in `performance-review.md` are proposed acceptance thresholds, not claimed baselines.
- Dependency vulnerabilities and legal obligations were not asserted from package names alone. The repository lacks automated vulnerability, SBOM, and license reports; generating and reviewing those reports is a recommendation.

## Related audit documents

- `architecture-risks.md` — module boundaries, workflow safety, provider seams, and refactoring triggers.
- `test-coverage-review.md` — current test evidence and missing test lanes.
- `performance-review.md` — GPU/runtime evidence, bottlenecks, memory, and measurable goals.
- `security-and-account-linking.md` — credentials, OAuth, shared destinations, publishing, and updates.
- `recommended-feature-order.md` — dependency-safe roadmap in small changes.
- `maintenance-plan.md` — five-feature maintenance cadence, Git/OpenSpec hygiene, release and install checks.
- `database-roadmap.md` — schema evolution and SQLite operating model.
- `ui-ux-roadmap.md` — 1440p-first, accessibility, high-DPI, playback, and timeline sequence.
