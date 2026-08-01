# Test Coverage Review

## Current evidence

The repository contains 61 pytest tests across nine modules. No coverage tool or threshold is configured, so this audit does not claim a line or branch percentage. `pyproject.toml` runs tests from `tests/`, uses Ruff's E/F/I/UP rules, and uses Pyright `standard` mode. There is no tracked CI workflow.

### What is covered well

| Area | Evidence | Assessment |
|---|---|---|
| ffprobe parsing | `tests/test_media.py` covers normal JSON, missing video stream, and missing FFmpeg guidance. | **Medium strength — Verified** |
| CUDA discovery | `tests/test_transcription.py` covers CUDA/CPU selection, packaged DLL directories, registration, missing DLLs, and temp cleanup on failure. | **High strength for pure selection logic — Verified** |
| Transcript search | `tests/test_transcript_search.py` covers case folding, exact data preservation, empty search, and wraparound navigation. | **High strength — Verified** |
| Candidate analysis | `tests/test_clip_detection.py` covers batching, overlap, parsing, source-derived timestamps, visual-claim sanitization, boundary penalties/merge, Ollama 0.32.5 shapes, model discovery, and connection diagnostics. | **High unit strength — Verified** |
| SQLite projects | `tests/test_projects.py` covers schema v1, future-version rejection, foreign keys, recent limit, exact round trip, source invalidation, atomic replacement, malformed JSON, and missing media. | **High unit strength — Verified** |
| Project and candidate UI | Offscreen tests cover activation, restore, failed load, missing VOD, persistence failure, candidate details, and scrollability. | **Medium strength — Verified** |
| Theme | `tests/test_theme.py` asserts palette tokens and major selectors exist. | **Low behavioral strength — Verified** |

## High-priority gaps

### High — no real runtime integration lane (Verified)

All external operations are mocked or bypassed. There is no test that runs a small licensed fixture through ffprobe/FFmpeg, faster-whisper CPU, CUDA (optional hardware lane), live Ollama, or the complete probe-to-save workflow. Mock tests verify calls and shapes but cannot detect executable discovery, DLL/freezer layout, codec, driver, model-download, HTTP compatibility, or subprocess encoding failures.

**Recommended changes:**

1. Add a tiny generated audio/video fixture with documented provenance; run ffprobe and FFmpeg on Windows CI where available.
2. Add opt-in markers for `integration`, `gpu`, and `ollama`; keep default tests fast.
3. Run a live Ollama contract test against the minimum supported version/model in a controlled nightly/manual lane.
4. Add a packaged executable smoke test on a clean Windows VM.

### High — job lifecycle and thread behavior are untested (Verified)

The suite calls `ClipAnalysisTask.run()` directly but does not exercise `QThreadPool`, queued signal delivery, UI thread affinity, close during work, cancellation, stale results, concurrent clicks, or unexpected worker exceptions. This is the most consequential regression gap for responsiveness.

**Required scenarios for a job-lifecycle change:**

- every task produces exactly one terminal outcome;
- unexpected exception restores all controls and preserves durable state;
- close/cancel terminates owned subprocesses and removes temporary files;
- stale result from project A cannot update project B;
- CPU retry cannot overlap the failed CUDA job;
- UI heartbeat remains responsive under mocked long work;
- application shutdown does not hang or leave FFmpeg/model work orphaned.

### High — database operational failure coverage is incomplete (Verified)

Tests validate transactional replacement and malformed JSON, but not lock contention, disk full/read-only directory, interrupted migration, corrupt database, backup/restore, WAL sidecars, schema integrity, or simultaneous readers/writer. `ProjectRepository._connect` is used directly in a test, coupling the test to a private method.

**Required scenarios:** busy timeout and actionable lock errors; failed migration preserves a restorable backup; corruption produces recovery guidance; path/permission errors retain old UI state; large transcript load/save meets timing and memory budgets; candidate-to-transcript invariants cannot be violated.

### High — security/account/publishing tests do not exist (Future risk)

This is expected because those features are deferred. They become release-blocking before account linking:

- OAuth state, nonce, PKCE, callback port collision, cancellation, expiry, revocation, and wrong-account tests;
- credential-store tests proving tokens never enter SQLite, logs, crash reports, environment dumps, or Git;
- scope and account-isolation tests for multiple Twitch accounts and shared destinations;
- idempotency, retry classification, rate limits, duplicate-publish prevention, and authorization-expired recovery;
- malicious transcript/model output cannot invoke tools, change destinations, or publish without a user/automation policy decision;
- signed-update tamper, downgrade, revoked key, partial download, and rollback tests.

## Medium-priority gaps

- **Verified:** `parse_ffprobe_output` lacks tests for zero/invalid frame-rate fractions, missing duration, audio-less video, multiple video/audio streams, variable frame rate, and zero/unknown bitrate.
- **Verified:** `extract_audio` lacks subprocess timeout, permission, disk-full, Unicode/long path, damaged media, and cancellation tests.
- **Verified:** faster-whisper execution lacks model-load failure, CUDA out-of-memory, mid-generator failure, empty transcript, language/encoding, progress monotonicity, and successful cleanup tests.
- **Verified:** `OllamaClient._request_json` lacks HTTP error bodies that are JSON arrays/scalars, non-UTF-8 bodies, timeout variants, response-size limits, partial `done=false`, cancellation, and retry classification.
- **Verified:** candidate parsing silently skips invalid candidates; there is no test or metric for partial rejection count, duplicate semantic types, very large model responses, or prompt-injection text.
- **Verified:** `merge_and_rank_candidates` lacks tests for transitive overlaps, multiple possible merge targets, same story with different clip-type labels, equal-score determinism, and high candidate counts.
- **Verified:** project UI lacks tests for failed `Path.stat`, ffprobe failure preserving a previous source, save-video failure control state, repeated rapid dialog actions, and errors longer than the status area.
- **Verified:** no tests cover daylight-saving timestamps, Windows reserved names, UNC paths, paths over 260 characters, non-BMP Unicode, removable/network drives, or case-only path differences.
- **Verified:** no screen-reader, keyboard-only, focus-order, shortcut, contrast, high-contrast-mode, 1440p, mixed-DPI, or multi-monitor automated/manual evidence exists.
- **Verified:** there is no startup-time, DB latency, transcription speed, AI latency, memory, VRAM, disk-growth, or soak benchmark suite.

## Low-priority gaps

- Theme tests confirm stylesheet strings, not rendered states or contrast.
- Formatting helpers lack negative, infinity, NaN, and extreme-duration tests; upstream validation should normally reject these values.
- Dialog selection behavior with zero or many thousands of projects is not tested; pagination/search is explicitly deferred.

## Recommended test pyramid

1. **Per-change default lane:** pure unit tests, repository tests against temporary SQLite, offscreen Qt tests, Ruff, Pyright; target under 90 seconds on a normal Windows developer machine.
2. **Windows integration lane:** real ffprobe/FFmpeg fixture, filesystem/path matrix, application process launch, SQLite lock/recovery; target under 10 minutes.
3. **Local AI contract lane:** optional faster-whisper CPU, supported CUDA hardware, and live Ollama minimum/current versions; run nightly and before release.
4. **Packaged clean-machine lane:** signed-candidate executable/installer in a Windows VM with prerequisites absent/present; verify install, run, upgrade, repair, uninstall, and data preservation.
5. **Platform sandbox lane:** one isolated account per provider plus rate-limit/error simulations; required only when a platform adapter is approved.

## Coverage policy recommendation

- Add `pytest-cov` only in an approved test-infrastructure change.
- Establish a baseline before setting a gate. A reasonable first gate is at least 80% branch coverage for pure domain/persistence modules and no decrease on changed lines; Qt presentation code should be governed by behavior scenarios rather than chasing a blanket percentage.
- Require tests for every fixed production regression.
- Mark hardware/network tests explicitly; never make the fast local suite depend on the user's GPU, Ollama service, model cache, or social credentials.
- Keep test data outside Git when it is large or licensed; generate tiny deterministic fixtures when possible.

## Release test checklist

- [ ] Default unit/UI suite passes from a clean checkout.
- [ ] Coverage report is generated and changed-line gate passes.
- [ ] Real FFmpeg/ffprobe integration passes on supported Windows versions.
- [ ] CPU transcription and the supported NVIDIA GPU matrix pass.
- [ ] Minimum/current supported Ollama versions and configured model discovery pass.
- [ ] Database migration, backup, restore, corruption, lock, and disk-full scenarios pass.
- [ ] Cancellation, close, stale-result, and subprocess cleanup scenarios pass.
- [ ] 1440p, mixed-DPI, multi-monitor, keyboard, screen-reader, and contrast matrix passes.
- [ ] Packaged install/upgrade/repair/uninstall smoke tests pass on a clean VM.
- [ ] If accounts exist, token isolation/redaction/revocation and provider sandbox tests pass.
- [ ] If updates exist, signature/tamper/downgrade/rollback tests pass.
