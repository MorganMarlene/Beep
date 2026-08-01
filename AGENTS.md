# Instructions for Coding Agents

These instructions apply to the entire Spotlight repository.

1. Read `README.md`, `docs/architecture.md`, `docs/development-roadmap.md`, and every applicable architecture decision in `docs/decisions/` before changing code.
2. Build only the currently approved milestone. The active milestone is defined in `docs/development-roadmap.md`.
3. Never silently add features, dependencies, infrastructure, or scope. If a useful change is outside the approved milestone, explain it and request approval before implementing it.
4. Prefer simple, readable code over premature abstraction. Add layers and interfaces only when they serve a current requirement or materially improve testability.
5. Keep all long-running work off the PySide6 UI thread. Communicate results back to the UI using safe Qt mechanisms.
6. Use type hints for application code and keep type boundaries clear.
7. Add tests for important logic, especially parsing, persistence, workflow coordination, and regressions.
8. Keep videos, extracted audio, databases, temporary media, model weights, and other generated or large files outside the Git repository.
9. Assume Windows is the primary operating system. Treat Windows paths, subprocess behavior, packaging, and installation as first-class concerns.
10. Use only free and locally runnable tools for application functionality unless a future approved milestone explicitly changes that constraint.
11. Explain every required installation and setup step clearly, including how the user can verify that each prerequisite works.
12. Do not implement deferred roadmap items or create speculative scaffolding for them.
13. Preserve user data. Never overwrite or delete an original video, and make cleanup behavior explicit and safe.
14. Keep credentials and machine-specific configuration out of source control.

## Current scope

Version 0.1 is limited to local video selection, ffprobe metadata display, FFmpeg audio extraction, local faster-whisper transcription, timestamped transcript interaction, and SQLite persistence.

Twitch downloading, Ollama, AI clip scoring, automatic clipping, vertical rendering, captions, face detection, subject tracking, platform exports, automatic posting, and complex worker systems are not approved.

## Completed feature Git workflow

For every completed feature:

1. Run pytest.
2. Run Ruff lint.
3. Run Ruff formatting check.
4. Run Pyright.
5. Do not commit if validation fails.
6. Create a clear Conventional Commit message.
7. Commit only files related to the approved feature.
8. Push the completed commit to `origin/main`.
9. Never commit local media, models, databases, transcripts, exports, caches, temporary files, secrets, or `.venv`.
10. Report the commit hash and push result.
