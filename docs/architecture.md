# BEEP Version 0.1 Architecture

## Purpose

Version 0.1 validates one complete local workflow: select a video, inspect it, extract its audio, transcribe it, display the transcript, and persist the result. The architecture must support that workflow without introducing infrastructure for unapproved future features.

## Architectural style

BEEP 0.1 is a small modular monolith. It runs as one desktop application, uses one SQLite database, and delegates only long-running work to a minimal background execution mechanism.

The design uses a few clear boundaries:

- Presentation owns PySide6 widgets and user interaction.
- Application logic coordinates the import and transcription workflow.
- Media integrations invoke ffprobe and FFmpeg.
- Transcription integrates with faster-whisper.
- Persistence reads and writes SQLite data.

These boundaries are intended to keep responsibilities clear, not to create a framework. Version 0.1 should use direct, readable code and introduce interfaces only where they improve testing or isolate an external tool.

## Proposed implementation layout

The following layout is approved for implementation planning but should be created only as files become necessary:

```text
src/spotlight/
├── __init__.py
├── __main__.py
├── application.py
├── config.py
├── models.py
├── database.py
├── media.py
├── transcription.py
├── workers.py
└── ui/
    ├── main_window.py
    └── transcript_view.py

tests/
├── test_database.py
├── test_media.py
└── test_transcription.py
```

This is intentionally flatter than the long-term architecture. Modules should be split only when their size or responsibilities justify doing so.

## Responsibilities

### Application entry point

Creates the Qt application, initializes application paths and the database, constructs dependencies, and opens the main window. Startup should detect missing external requirements and present understandable errors.

### User interface

The basic window owns:

- A control for selecting one local video
- A metadata area showing filename, duration, resolution, and frame rate
- A transcription action and progress/status display
- A timestamped transcript list
- A detail area showing the selected segment's start and end timestamps
- Clear failure and cancellation feedback

The UI does not invoke subprocesses, run inference, or execute database queries directly. It delegates work and responds to signals or callbacks.

### Application coordinator

Coordinates the use case in this order:

1. Validate the selected path.
2. Read metadata using ffprobe.
3. Create or update the project record.
4. Extract audio using FFmpeg.
5. Transcribe audio using faster-whisper.
6. Store transcript segments transactionally.
7. Return results for display.

It also controls error propagation and ensures partial failures leave the project in an understandable state.

### Media module

The media module builds and executes argument-list subprocess calls for `ffprobe` and FFmpeg. It parses ffprobe's JSON output and converts it into typed application data.

It is responsible for:

- Detecting inaccessible or unsupported media
- Selecting the primary video stream
- Calculating a reliable duration
- Parsing rational frame rates such as `30000/1001`
- Reporting resolution
- Extracting transcription-ready audio
- Returning actionable errors without exposing raw subprocess details as the only user message

FFmpeg commands must not be assembled as shell strings. Argument lists avoid quoting and path-handling errors on Windows.

### Transcription module

The transcription module owns faster-whisper model loading and transcription. It returns ordered segments containing text, start time, and end time.

Version 0.1 does not require word-level timestamps, diarization, summarization, or language-model analysis. Model name, device choice, and compute type may be simple configuration values, with safe CPU-compatible defaults documented during implementation.

### Persistence module

SQLite stores structured state. A small explicit data-access layer is preferred over an ORM for Version 0.1 unless implementation evidence shows an ORM materially reduces complexity.

The minimum conceptual schema is:

```text
projects
- id
- source_path
- filename
- duration_seconds
- width
- height
- frame_rate
- status
- created_at
- updated_at

transcript_segments
- id
- project_id
- segment_index
- start_seconds
- end_seconds
- text
```

The database should enforce project ownership and transcript ordering with appropriate foreign-key, uniqueness, and index constraints. Schema creation and future migration behavior must be deterministic.

Paths stored in SQLite should refer to media outside the Git repository. Source videos and model files are never copied into version control.

## Keeping the UI responsive

Media probing may be short, but audio extraction and transcription are long-running operations. They must not execute on the PySide6 UI thread.

Version 0.1 should use the smallest Qt-compatible background design that provides:

- A single active processing task
- Progress and status updates where available
- Error delivery back to the UI
- Safe UI updates through Qt signals
- Clean shutdown behavior
- Cancellation if it can be implemented safely without expanding the milestone

A thread-backed Qt worker is acceptable for coordinating FFmpeg and faster-whisper because their intensive work occurs in subprocesses or native libraries. A custom process pool, persistent job queue, distributed system, and generalized workflow engine are out of scope.

## Data and file locations

The SQLite database, extracted audio, logs, models, and temporary files should live in an appropriate per-user application-data location on Windows, not beside the source code.

A project references the original selected video rather than copying it. Extracted audio is derived data and may be safely regenerated. Cleanup behavior must avoid deleting the user's original video.

## Error handling

Expected failures should become clear user-facing messages, including:

- Missing FFmpeg or ffprobe
- Invalid or inaccessible video paths
- Unsupported or corrupt media
- Audio extraction failure
- Model download or loading failure
- Transcription failure
- Database initialization or write failure

Detailed technical context should be logged locally. User-facing messages should say what failed and how to correct it when possible.

## Testing boundaries

Important logic should be testable without opening the full desktop window or processing a large video. Tests should cover:

- ffprobe JSON parsing, including rational frame rates
- Timestamp formatting
- Transcript segment ordering and validation
- SQLite inserts, reads, replacement behavior, and constraints
- Application workflow behavior with media and transcriber test doubles
- UI selection behavior where it provides meaningful confidence

A very small generated media fixture may be used for focused FFmpeg integration testing, but large videos and model weights must never enter Git.

## Deferred architecture

No components for downloading, clip scoring, editing, rendering, captions, computer vision, publishing, or Ollama should be added in Version 0.1. Future milestones may extend the modular monolith after their behavior is explicitly approved.
