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

The approved scope includes local video selection, ffprobe metadata display,
FFmpeg audio extraction, local faster-whisper transcription, timestamped
transcript interaction, transcript search, the `add-ai-clip-detection` OpenSpec
change, and the `add-projects-system` OpenSpec change. Clip detection must use
Ollama as its sole AI runtime and remain local-only and responsive. Saved projects
persist metadata, transcript segments, and validated candidates in local SQLite;
candidate results without a saved project remain in memory only.
The `embedded-video-workspace` OpenSpec change additionally approves local MP4
and MOV review playback, a central source-time clock, and synchronized transcript
and clip-candidate seeking. Playback remains read-only and project-independent.

Twitch downloading, remote AI, additional AI SDKs/runtimes, automatic clipping,
vertical rendering, captions, visual detection, face detection, subject tracking,
video editing, platform exports, scheduling, automatic posting,
reusable profiles, project rename, deletion, duplication, search, pinning,
missing-media relinking, automatic reopening, and complex worker systems are not
approved.

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
