# Spotlight Development Roadmap

## Active milestone: Version 0.1

Only Version 0.1 is approved for implementation. Later milestones are intentionally undefined and must not be anticipated in code.

## Version 0.1 objective

Deliver a small, usable Windows desktop application that turns one selected local video into a persisted, timestamped transcript while keeping the interface responsive.

## Implementation sequence

### 1. Project foundation

- Establish the minimal Python package and PySide6 entry point.
- Configure type checking, linting, and tests.
- Define Windows application-data paths.
- Document installation and verification for Python, FFmpeg, and faster-whisper.
- Add startup checks for required external tools.

Completion means the basic window launches and development checks run successfully.

### 2. Media selection and inspection

- Add selection of one local video through a native file dialog.
- Invoke ffprobe without blocking the UI.
- Parse filename, duration, resolution, and frame rate.
- Display those values in the window.
- Handle invalid media and missing ffprobe clearly.
- Add unit tests for metadata parsing.

Completion means a supported local video can be selected and its required metadata is displayed accurately.

### 3. SQLite persistence

- Create the minimal project and transcript-segment schema.
- Initialize the database in the per-user application-data directory.
- Persist the selected video's path and metadata.
- Load stored project and transcript data.
- Add database tests using isolated temporary databases.

Completion means project metadata survives an application restart.

### 4. Audio extraction

- Define a transcription-ready audio format.
- Extract audio with FFmpeg outside the UI thread.
- Store derived audio outside the repository.
- Surface progress or clear indeterminate status.
- Handle failure without corrupting the saved project.
- Add focused command-building and integration tests.

Completion means Spotlight reliably produces local audio suitable for faster-whisper while the window remains responsive.

### 5. Local transcription

- Load a documented faster-whisper model locally.
- Transcribe extracted audio outside the UI thread.
- Produce ordered segments with start time, end time, and text.
- Persist completed segments transactionally.
- Report model loading and transcription errors clearly.
- Add tests around segment conversion and workflow behavior.

Completion means a selected video can be transcribed entirely on the local computer and restored from SQLite.

### 6. Transcript interaction

- Display timestamped transcript segments in the window.
- Let the user select one segment.
- Display that segment's precise start and end timestamps.
- Preserve correct ordering for long transcripts.
- Add a focused UI test for segment selection.

Completion means the full approved user workflow is usable.

### 7. Version 0.1 stabilization

- Test representative video formats and Windows paths, including spaces and non-ASCII characters.
- Verify startup, processing, restart, and failure recovery behavior.
- Review logs and user-facing error messages.
- Verify that no source video, extracted audio, model file, database, or temporary artifact is tracked by Git.
- Document all installation and first-run steps.

Completion means Version 0.1 satisfies every acceptance criterion below without implementing deferred features.

## Version 0.1 acceptance criteria

- The user can select exactly one local video for the active workflow.
- The UI displays its filename, duration, resolution, and frame rate from ffprobe data.
- FFmpeg extracts its audio successfully.
- faster-whisper transcribes the audio locally.
- The UI remains responsive throughout long-running operations.
- Transcript segments appear in timestamp order.
- Selecting a segment displays its start and end timestamps.
- Project metadata and transcript segments persist in SQLite.
- Common failures produce understandable messages.
- Important parsing, persistence, and coordination logic has automated tests.
- Processing does not require a paid or cloud-hosted service.
- No explicitly deferred feature is present.

## Deferred work

The following work has no approved implementation milestone:

- Twitch downloading
- Ollama integration
- AI highlight or clip scoring
- Automatic clip creation
- Vertical video rendering
- Video captions
- Face detection
- Subject tracking
- Platform export workflows
- Automatic posting

Adding any of these items requires explicit scope approval and a roadmap update first.

