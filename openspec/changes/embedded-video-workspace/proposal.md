## Why

Creators currently have to leave BEEP to verify transcript context and AI clip candidates against the source VOD. An embedded, synchronized local player makes candidate review immediate while preserving BEEP's project-centered, local-only workflow.

## What Changes

- Make an embedded local video player the primary workspace for supported MP4 and MOV project sources.
- Add basic playback controls, a seekable timeline, and a continuously displayed current playback time.
- Let users seek to any valid source timestamp without blocking the UI.
- Seek playback to an AI clip candidate's start when that candidate is activated.
- Seek playback to a transcript segment's start when its timestamp is activated.
- Keep player position, timeline, transcript, and candidate selection synchronized, including an active transcript-section highlight.
- Preserve the active project indicator, restored project media paths, transcripts, candidates, GPU transcription, and local Ollama clip detection.
- Require exact transcript evidence for every AI candidate, generate factual English summaries and reasons from that evidence, and rank for explicit viral signals instead of generic dialogue.
- Use a responsive 1440p-first layout that remains usable at 1080p and scales cleanly at 4K.
- Keep all playback local. This version does not add editing, trimming, exporting, captions, vertical rendering, publishing, Twitch integration, or new persistence behavior.

## Capabilities

### New Capabilities

- `embedded-video-workspace`: Local MP4/MOV playback, time-based seeking, synchronized transcript/candidate navigation, responsive workspace layout, and project-aware playback failure handling.

### Modified Capabilities

- `clip-candidate-ranking`: Require grounded English output and deterministic viral-signal prioritization while preserving project persistence and local-only Ollama inference.

## Impact

- Affects the PySide6 main workspace, transcript presentation, candidate interaction, playback state coordination, and UI tests.
- Introduces use of PySide6's local multimedia facilities and requires Windows packaging/runtime verification for the selected Qt multimedia backend and supported codecs.
- Does not change the SQLite schema, persisted candidate shape, transcription device selection, Ollama runtime, or media files.
- Requires small local media fixtures or controllable playback test doubles; large VODs remain outside Git.
