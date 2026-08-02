# BEEP

BEEP is a local Windows desktop application for working with video content. The approved Version 0.1 milestone imports one local video, reads its metadata, extracts its audio, transcribes it locally, and presents a timestamped transcript.

Version 0.1 is deliberately small. It is intended to establish a dependable end-to-end foundation before any clip creation or broader AI automation is considered.

## Version 0.1 scope

BEEP 0.1 will:

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

1. Launch BEEP.
2. Select a local video.
3. Review the detected video metadata.
4. Start transcription.
5. Monitor progress while the interface remains responsive.
6. Browse the timestamped transcript.
7. Select a segment to inspect its start and end times.
8. Close and reopen the application without losing the stored project and transcript.

## Local AI clip detection

After transcription, BEEP can use a local Ollama model to generate an explainable,
ranked list of clip candidates. Version 1 analyzes transcript text only and never
sends prompts or content to a remote AI service. Candidates belonging to a saved
project are stored locally; results without a saved project remain in memory for
the current session only.

Each candidate includes source-derived timestamps, clip type, score, summary,
selection reasoning, strong signals, and weaknesses or missing context. BEEP does
not claim that transcript analysis detected facial reactions, menus, loading
screens, or other visual-only events. Editing, exporting, scheduling, and posting
remain out of scope.

### Ollama setup on Windows

1. Download and run the official `OllamaSetup.exe` from
   https://ollama.com/download/windows. The installer runs Ollama in the
   background and adds `ollama` to the user PATH.
2. Open a new PowerShell window and download the default local model:

   ```powershell
   ollama pull qwen2.5:7b
   ```

3. Verify the runtime and model:

   ```powershell
   ollama list
   ollama run qwen2.5:7b "Reply with OK"
   ```

BEEP connects only to Ollama's loopback endpoint at `127.0.0.1:11434`. To select
another locally installed Ollama model for a session, set `BEEP_OLLAMA_MODEL`
before launching BEEP. No Ollama Python SDK or other AI runtime is required.

Clip analysis uses 4,000-character overlapping batches and allows each local
`/api/generate` request up to 600 seconds by default. These limits can be adjusted
for slower or faster local hardware before launching BEEP:

```powershell
$env:BEEP_OLLAMA_BATCH_CHARACTER_LIMIT = "4000"
$env:BEEP_OLLAMA_REQUEST_TIMEOUT_SECONDS = "600"
uv run beep
```

Both settings must be positive whole numbers. If a later batch fails, BEEP keeps
validated candidates from successful batches in memory, identifies the failed
batch, and preserves the project's last complete saved candidate set.

## Local projects

BEEP starts without automatically opening a project. Use **New Project** to create
a project with a required project name and an optional **Brand name**, or use
**Open Project** to restore existing work. Brand name is descriptive metadata on
that project only; it is not a reusable profile.

The sidebar shows the 10 most recent projects and the active project name. A saved
project restores its VOD metadata, exact timestamped transcript, and validated AI
clip candidates without rerunning ffprobe, faster-whisper, or Ollama.

Project data is stored in local SQLite at:

```text
%LOCALAPPDATA%\BEEP\projects.sqlite3
```

SQLite contains structured data and the original VOD path only. BEEP never copies
video or audio into the database. If a VOD is moved or deleted, BEEP restores the
saved transcript and candidates, marks the source unavailable, and disables work
that needs the media file. Version 1 does not search for or relink missing media.

To back up projects, close BEEP and copy `projects.sqlite3` together with any
adjacent `projects.sqlite3-wal` and `projects.sqlite3-shm` files if present. The
database remains local and is ignored by Git.

Project rename, deletion, duplication, search, pinning, relinking, automatic
reopening, reusable profiles, Twitch importing, editing, exports, titles,
descriptions, thumbnails, and posting are not part of this version.

## Embedded local video review

BEEP can play the active project's local MP4 or MOV source inside the review
workspace. Playback, the timeline, transcript segments, and ranked clip
candidates share one source-relative clock. Activating a transcript timestamp or
candidate seeks to its stored start time, and playback highlights the current
transcript segment and applicable highest-ranked candidate.

Version 1 is verified with H.264 video and AAC audio in MP4 and MOV containers on
Windows. Qt Multimedia uses the platform-selected decoder; BEEP does not claim
that video decoding is using CUDA or NVDEC. Other codec combinations may fail
with the backend's real error. Qt seeking is responsive but is not guaranteed to
be frame-accurate, especially for long-GOP or variable-frame-rate media.

Playback streams the original local file and does not load the complete VOD or
copy decoded frames into Python. It never edits, trims, exports, captions, or
modifies the source.

To run the optional real-backend tests in PowerShell:

```powershell
$env:BEEP_RUN_PLAYBACK_INTEGRATION = "1"
uv run pytest tests/test_playback_integration.py -q -s
```

The test creates temporary H.264/AAC fixtures with FFmpeg and deletes them with
the pytest temporary directory. See `docs/playback-verification.md` for manual
acceptance steps and limitations.

## Installation status

Install the Python environment with `uv sync`, configure FFmpeg and faster-whisper
as described by the application errors, and follow the Ollama steps above before
using local clip analysis. Keep downloaded models and generated media outside Git.

## Project documentation

- `docs/architecture.md` defines the Version 0.1 design.
- `docs/development-roadmap.md` defines the approved implementation sequence.
- `docs/decisions/ADR-0001-modular-monolith.md` records the initial architectural decision.
- `AGENTS.md` contains mandatory instructions for coding agents.

## License

BEEP is released under the MIT License. See `LICENSE` for the full license text.
