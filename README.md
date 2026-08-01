# Spotlight

Spotlight is a local Windows desktop application for working with video content. The approved Version 0.1 milestone imports one local video, reads its metadata, extracts its audio, transcribes it locally, and presents a timestamped transcript.

Version 0.1 is deliberately small. It is intended to establish a dependable end-to-end foundation before any clip creation or broader AI automation is considered.

## Version 0.1 scope

Spotlight 0.1 will:

1. Let the user select one local video file.
2. Use `ffprobe` to read and display its filename, duration, resolution, and frame rate.
3. Use FFmpeg to extract audio to a temporary or application-data location.
4. Use faster-whisper to transcribe the audio locally.
5. Display timestamped transcript segments in a basic PySide6 window.
6. Show the selected segment's start and end timestamps.
7. Store project metadata and transcript data in SQLite.

## Explicitly out of scope

Version 0.1 will not include:

- Twitch downloading
- Ollama or other language-model integration
- AI clip scoring
- Automatic clipping
- Vertical rendering
- Captions burned into video
- Face detection or subject tracking
- Platform-specific exports
- Automatic posting
- A general-purpose job system or complex worker architecture

These features require separate approval before implementation.

## Technology direction

- Python is the application language.
- PySide6 provides the desktop interface.
- FFmpeg and ffprobe handle media operations and inspection.
- faster-whisper provides local transcription.
- SQLite stores project and transcript records.
- Long-running media and transcription operations run outside the PySide6 UI thread.
- All processing remains local, using free and locally runnable tools.

## Intended Version 0.1 workflow

1. Launch Spotlight.
2. Select a local video.
3. Review the detected video metadata.
4. Start transcription.
5. Monitor progress while the interface remains responsive.
6. Browse the timestamped transcript.
7. Select a segment to inspect its start and end times.
8. Close and reopen the application without losing the stored project and transcript.

## Installation status

Application code and installation instructions have not yet been created. When implementation begins, all Windows prerequisites—including Python, FFmpeg, and the selected faster-whisper model—must be documented with clear verification steps.

## Project documentation

- `docs/architecture.md` defines the Version 0.1 design.
- `docs/development-roadmap.md` defines the approved implementation sequence.
- `docs/decisions/ADR-0001-modular-monolith.md` records the initial architectural decision.
- `AGENTS.md` contains mandatory instructions for coding agents.

