## Context

See `proposal.md` for motivation. BEEP is a PySide6 modular monolith with one active project, a persisted local source path, a timestamped transcript, ranked candidates, and background transcription/analysis tasks. The current `SpotlightWindow` owns the main layout and displays transcript and candidates without playback. Source media stays outside SQLite and may be missing when a project is restored.

Playback must use the same source-relative time domain as transcript/candidate seconds, remain local and read-only, avoid blocking the Qt event loop, and coexist with the current CUDA transcription and Ollama workflows. Version 1 supports representative H.264/AAC MP4 and MOV sources through the Windows Qt multimedia backend; unsupported codec combinations require an actionable failure rather than a fallback transcoding feature.

## Goals / Non-Goals

**Goals:**

- Add one testable playback boundary around Qt Multimedia rather than placing media state directly throughout the main window.
- Make video dominant at 1440p while keeping transcript, candidates, active project, timeline, controls, and status usable across the required resolutions.
- Maintain one canonical source-time coordinate and deterministic one-to-many synchronization with immutable transcript/candidate timestamps.
- Handle source load, project switch, playback errors, seeking, and shutdown without stale callbacks or UI blocking.
- Preserve current project persistence, transcript search, candidate details/ranking, CUDA/CPU transcription, and local Ollama analysis.

**Non-Goals:**

- Frame-accurate editing, in/out boundaries, trimming, transcoding, rendering, export, captions, vertical layouts, computer vision, publishing, or Twitch ingest.
- Persisting playback position, layout proportions, or new media state in SQLite.
- A general media-engine plugin system or arbitrary codec installation manager.
- Parallel media-processing orchestration beyond the current approved tasks.

## Decisions

### 1. Use Qt Multimedia behind a narrow playback controller

Add a focused playback module with a project-agnostic playback protocol and a Qt `QObject` adapter that owns `QMediaPlayer` and `QAudioOutput`. A bounded video-surface wrapper hides the Qt video output widget from the rest of the workspace. The protocol exposes typed commands for source load/clear, play, pause, and seek plus notifications for source identity, duration, position, playback state, seeking state, and detailed errors. Protocol values contain no `ProjectSnapshot`, database, profile, Twitch-account, or Qt media-player types.

`QMediaPlayer` remains on the Qt application thread because its API and signal lifecycle are event-driven and thread-affine; native demux/decode is delegated asynchronously by Qt's multimedia backend. No file reads, decoding loops, FFmpeg subprocess, frame conversion, or polling loop is added to the UI thread. A small protocol permits deterministic fake-controller UI tests and a later playback-backend replacement without redesigning the workspace.

Qt Multimedia is the Version 1 review backend, not a promise of frame-accurate decoding. `QMediaPlayer.setPosition()` may resolve to the closest frame its backend can decode. A future frame-accurate backend based on measured product needs may implement the same playback protocol and video-surface boundary with precise presentation timestamps and frame stepping. The workspace, project coordinator, transcript view, and candidate view must not call `QMediaPlayer` directly.

Alternatives considered:

- Launching an external player would break the synchronized in-app review goal.
- Manual FFmpeg/OpenCV decoding would add queues, audio/video clocking, frame conversion, and cancellation complexity outside Version 1.
- A VLC/libmpv dependency could broaden codec behavior but adds native distribution and licensing/packaging work not justified before Qt Multimedia is tested against the required fixtures.

### 2. Use integer source microseconds as the application coordination time base

The application-facing playback protocol accepts and emits integer microseconds relative to the original source start. The Qt adapter converts to and from Qt's integer-millisecond API at its boundary. Transcript and candidate floating-point seconds remain unchanged in their domain objects and persistence; navigation converts them once into source microseconds. Seek requests are clamped to `[0, duration]` when duration is known.

One playback-clock coordinator owns the current source identity, duration, requested position, and effective position. It publishes immutable clock snapshots to any number of presentation subscribers. Player events drive current-time text, the Version 1 timeline, active transcript lookup, and active candidate indication; no timeline or panel owns the player. Transcript lookup uses ordered segment boundaries and binary search rather than scanning all segments on every position event. Candidate lookup may initially scan the small ranked set; if ranges overlap, the first/highest-ranked matching candidate is active.

User intent and state reflection use different signal paths. Candidate/transcript/timeline activation emits one seek intent; subsequent player position updates update presentation only and never emit another seek. The clock's publish/subscribe shape allows later overview, edit, caption, or comparison timelines to observe the same source clock without chaining timelines together. Playback-driven highlighting does not replace transcript search highlights or mutate user-selected text/candidate data.

Microseconds do not make Qt playback frame-accurate in Version 1. They avoid making milliseconds part of BEEP's domain contract and can represent later frame presentation timestamps. A future exact-seek implementation must additionally use source stream time-base and frame-index information rather than infer frames from nominal FPS, particularly for variable-frame-rate media.

Alternatives considered:

- Floating-point seconds everywhere risk rounding drift between Qt's millisecond API, timeline mapping, future word timestamps, and persisted timestamps.
- Frame numbers are unsuitable as the shared UI time base because sources may be variable-frame-rate and no editing/frame-accurate contract is approved.

### 3. Build a bounded video-workspace widget instead of expanding all layout code inline

Introduce a dedicated workspace widget composed of:

- a dominant video surface;
- play/pause, current time/duration, and a dedicated timeline view;
- the existing transcript/search behavior adapted to expose explicit timestamp activation and playback highlighting;
- the candidate list/details adapted to expose explicit candidate activation and playback highlighting;
- existing processing controls and status without changing their workflows.

The timeline view owns a single tested source-time-to-pixel/value transform and paints the playhead separately from its base track. Version 1 supplies no marker data, selection ranges, caption lanes, or edit handles. This keeps later AI candidate markers and multiple synchronized timeline views additive rather than forcing candidate data into a raw slider or the playback controller.

Use nested `QSplitter`/stretch-based layouts rather than new fixed panel dimensions. At 1440p, video receives the largest initial share and transcript/candidates remain visible. At 1080p, panes remain resizable/scrollable without hiding required controls. At 4K and supported mixed scaling, Qt logical sizing and the existing application stylesheet remain the base; no bitmap UI assets are required. Validate 100%, 125%, 150%, and 200% Windows scaling where the target resolution supports it, and never derive geometry directly from physical pixels.

The main window remains responsible for active-project orchestration, but media-specific widget/state code moves behind this boundary. This is a targeted extraction, not a general view framework.

### 4. Treat activation and playback-driven highlighting separately

Candidate clicks/activation seek to the candidate start; programmatic changes used to indicate the active playback range do not seek. Transcript timestamp activation carries the stable segment index and exact stored start time; playback position selects a distinct active-highlight layer.

The transcript renderer composes search matches, current search navigation, user selection, and playback-active highlighting in a deterministic priority order so playback updates do not erase search state. It identifies displayed text ranges independently of the stored segment objects and applies incremental formatting rather than rebuilding the document per tick. When playback is in a transcript gap, only the playback-active layer clears. A future word-timestamp model can therefore supply smaller text ranges to the same highlight layer; Version 1 neither requests nor synthesizes word timestamps.

### 5. Bind player source lifecycle to the active project without persistence changes

After a project snapshot is fully loaded, the main window supplies its available source path to the playback controller only when the extension is MP4 or MOV. Loading a new project first pauses/stops and clears the prior source, then replaces transcript/candidates, then loads the new source. Closing the window clears the source and releases player/audio resources.

A small application coordinator maps the active `ProjectSnapshot` to an immutable local-media source value containing only a generated source identity, path, and known metadata. The playback module never imports the project repository or reads/writes SQLite. A future reusable profile or Twitch-ingest workflow must likewise resolve an account-owned or downloaded VOD to a project-owned local path before passing that neutral source value to playback.

A monotonically increasing source generation or equivalent source identity guards asynchronous duration/position/error callbacks so callbacks from a released source cannot affect the newly active project. A missing source, unsupported extension, backend error, or unsupported codec changes only playback availability and diagnostics; restored transcript and candidates remain intact.

Playback position is session-only. Schema version 1 and every repository method remain unchanged.

### 6. Make responsiveness measurable and avoid synthetic progress claims

Timeline, candidate, and transcript seeks call the asynchronous controller immediately. The UI updates the requested slider/time state within 100 milliseconds and shows a non-blocking seeking state until the backend reports the effective position/frame. The documented integration fixture and reference system measure the 250-millisecond p95 target; slower damaged, remote, or unusually encoded files retain responsiveness but may exceed the presentation target and must show the state honestly.

Position-driven UI work is coalesced to a useful display cadence when backend events are more frequent than the UI needs. No database access, transcript reconstruction, or complete candidate rerender occurs for each position tick.

### 7. Use layered tests with a tiny local fixture

- Pure tests cover seconds/milliseconds conversion, clamping, time formatting, active transcript boundary lookup, overlapping candidate selection, and stale source identities.
- Offscreen Qt tests inject a fake playback controller to cover each navigation direction, non-recursive synchronization, project switch/clear, search-highlight preservation, disabled states, and responsive layouts.
- A gated Windows integration test generates tiny H.264/AAC MP4 and MOV fixtures into a temporary directory at test time, or consumes an explicitly configured external fixture path, to verify Qt backend load/play/seek/error behavior. No media fixture is committed to Git.
- Manual acceptance covers audible playback, 1440p/1080p/4K and mixed scaling, repeated seeks, long transcripts, missing files, project switching, playback during transcript search, transcription, and analysis.

### 8. Keep future media products outside the review player

Clip trimming, exporting, captions, and vertical generation will require a separate media-composition domain and FFmpeg render pipeline. They may consume the same original source identity and source-time coordinates, but they must not add edit decisions, caption cues, render settings, or output paths to the playback controller. The player remains a transport/preview boundary; future edit selections and timeline tracks remain independent presentation/application models.

This permits future trimming and frame-accurate preview to replace or extend the backend behind the playback protocol without redesigning project persistence or the surrounding workspace. It does not add any editing model, marker track, caption data, renderer, or export behavior in Version 1.

### 9. Treat hardware acceleration as an observable backend choice

Qt's selected Windows multimedia backend and the installed driver decide whether video decoding uses hardware acceleration. BEEP does not create a CUDA context for playback, claim NVDEC use, or couple playback to faster-whisper's CTranslate2 device selection. Diagnostics record the selected Qt backend when available, media error details, and whether Qt reports a usable video output; they must not promise a GPU decoder that Qt cannot confirm.

The video surface consumes native backend frames directly. Application code does not copy `QVideoFrame` data into Python buffers or retain a frame queue. Media is streamed from disk, and application-controlled caches are bounded independently of VOD duration. Concurrent video decode, CUDA transcription, and Ollama may compete for the RTX 3070 Ti's 8 GB VRAM; Version 1 preserves each workflow and surfaces real failures, while a later resource-scheduling change may coordinate them after measurement.

### 10. Keep platform policy outside the playback protocol

Windows 10/11 remains the supported and acceptance-tested target. Paths are converted with `QUrl.fromLocalFile`, path comparisons retain Windows case/drive semantics at the project boundary, and packaging verification covers the Qt multimedia plugins and required runtime libraries.

The application-facing protocol and clock coordinator contain no Windows media-session or Qt backend types. macOS and Linux support is not promised by this change, but a platform-specific adapter and codec acceptance matrix can be added later without changing project storage, transcript/candidate models, or synchronized workspace behavior.

### 11. Build accessibility into the widget boundaries

All interactive widgets expose accessible names, roles, values, and concise state text. Playback and review actions are keyboard-operable with a logical focus order and visible focus indicator. Seeking, active transcript, selection, search matches, and errors use text, focus, shape, or accessible state in addition to color. Theme states meet WCAG 2.1 AA contrast targets where Qt rendering permits measurement, and layout tests include increased text size and Windows scaling.

## Risks / Trade-offs

- **Windows codec/backend variability** → Define required H.264/AAC fixtures, report the native error, document supported prerequisites, and do not silently transcode.
- **Some compressed sources cannot present an arbitrary frame within 250 milliseconds** → Update requested position immediately, show a seeking state, measure p95 on reference fixtures, and report the backend's final effective position.
- **Playback callbacks can race project changes** → Clear old media first and reject callbacks whose source generation is no longer active.
- **Position signals can create seek loops or excessive repainting** → Separate user intent from reflected state and coalesce presentation updates.
- **Playback highlighting can erase transcript search/selection styling** → Compose independent highlight layers with tested priority.
- **Adding the player could further enlarge `SpotlightWindow`** → Place player-specific state and layout in a bounded workspace/controller rather than adding direct media logic to the window.
- **Headless CI may not provide multimedia/video output** → Keep most behavior under fake-controller tests and run real playback only in a gated Windows integration lane.
- **Video decoding may share GPU/VRAM with transcription or Ollama** → Do not change inference device policy; measure coexistence on the RTX 3070 Ti and preserve responsive controls/errors if the backend falls back or resources are constrained.

- **Qt Multimedia seeking is not frame-accurate** -> Keep exact seeking out of Version 1, preserve source-time precision, isolate Qt behind the playback protocol, and require stream time-base/frame-index support in a future backend before editing relies on exact frames.
- **A raw slider or direct panel-to-player wiring would block later marker tracks and multiple timelines** -> Centralize time mapping in the timeline view and publish clock snapshots to independent subscribers.
- **Word-level highlighting is not possible from segment-only transcription** -> Keep highlight ranges independent of transcript storage and add word timestamps only through a future transcription/schema change.
- **Future profiles or Twitch accounts could leak into playback state** -> Resolve every playable item to a neutral project-owned local source before binding playback; keep credentials and account identity outside playback.
- **Retained decoded frames or duration-sized caches could exhaust memory on long VODs** -> Stream through the native surface, retain no Python frame queue, and bound all presentation caches independently of source duration.
- **Non-Windows backends differ in codecs, seeking, and hardware acceleration** -> Keep the protocol platform-neutral while making each future platform pass its own codec and timing acceptance matrix.

## Migration Plan

1. Add the playback controller and pure time/synchronization logic with fake-controller tests.
2. Add the bounded video workspace and responsive layout without removing existing review/processing behavior.
3. Connect active-project source load/clear and explicit transcript/candidate/timeline activation.
4. Add playback-driven highlights, error states, performance instrumentation, and shutdown cleanup.
5. Run unit/UI/integration/manual resolution and Windows codec checks before enabling the workspace by default.

No database or project-data migration is required. Rollback removes the player/workspace integration and returns to the prior transcript/candidate layout; persisted projects, transcripts, candidates, and original media remain compatible and untouched.
