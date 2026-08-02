## 1. Playback foundation

- [x] 1.1 Define a project-agnostic playback protocol and clock snapshot using integer source microseconds, with no project, profile, database, Twitch-account, or Qt backend types in the public boundary.
- [x] 1.2 Add a Qt Multimedia adapter that owns `QMediaPlayer` and `QAudioOutput`, exposes load, clear, play, pause, and seek commands, and reports position, duration, seeking state, source identity, selected backend diagnostics when available, and detailed errors.
- [x] 1.3 Add pure seconds/microseconds/milliseconds conversion, seek clamping, time formatting, timeline mapping, active transcript lookup, and highest-ranked active candidate selection helpers.
- [x] 1.4 Add unit tests for time conversion and rounding, timeline mapping, transcript boundary and gap behavior, overlapping candidate ranges, source-generation rejection, and out-of-range seeks.

## 2. Embedded workspace UI

- [x] 2.1 Add a bounded video-workspace widget with a native video surface, play/pause control, current-time/duration display, dedicated seekable timeline view, transcript panel, candidate panel, active project indicator, and existing processing/status controls.
- [x] 2.2 Give the timeline one tested source-time mapping and separate base-track/playhead painting so later marker layers can be added without candidate data entering the playback adapter; do not add markers or edit ranges in Version 1.
- [x] 2.3 Use resizable splitter and stretch-based layouts with minimum sizes that remain usable at 1080p, are video-first at 1440p, and scale with Qt logical sizing at 4K and supported 100%, 125%, 150%, and 200% Windows scaling.
- [x] 2.4 Add accessible names, roles, values, state text, visible focus, logical keyboard order, non-color status cues, and contrast-aware active/search/selection styling for playback and review controls.
- [x] 2.5 Preserve the existing dark theme, transcript search/navigation, candidate details/ranking, and transcription and analysis controls without introducing editing or export actions.

## 3. Project-aware source lifecycle

- [x] 3.1 Map the fully loaded active project to a neutral immutable local-media source value before loading available MP4 and MOV paths, without allowing the playback module to import or write project persistence.
- [x] 3.2 Disable playback with an actionable status for missing, inaccessible, unsupported, or undecodable sources while preserving review data.
- [x] 3.3 Stop and release the prior source before project changes and application shutdown, and ignore stale playback callbacks using source identity or generation checks.
- [x] 3.4 Keep playback position and layout state session-only, leave SQLite schema version 1 unchanged, and verify restored transcript and candidate data remains usable when media is unavailable.

## 4. Synchronized review interactions

- [x] 4.1 Connect timeline activation, transcript timestamp activation, and candidate activation to one non-blocking seek-intent path that converts exact stored seconds to clamped source microseconds at the application boundary.
- [x] 4.2 Reflect player position in the timeline and current-time display without issuing recursive seeks, and coalesce overly frequent presentation updates.
- [x] 4.3 Highlight the start-inclusive/end-exclusive active transcript segment through independent text-range formatting while preserving search matches, current search navigation, selection, text, and timestamps and without rebuilding the transcript per tick.
- [x] 4.4 Indicate the highest-ranked candidate containing the current playback position without changing candidate order, scores, fields, or activation behavior.
- [x] 4.5 Show a non-blocking seeking state until the backend reports its effective position, while keeping playback and all review controls responsive.

## 5. Automated verification

- [x] 5.1 Add offscreen Qt tests with an injected fake playback protocol for play/pause state, each navigation source, multiple clock subscribers, non-recursive synchronization, search-highlight preservation, candidate activation, unavailable-media behavior, project switching, and shutdown cleanup.
- [x] 5.2 Add UI layout and accessibility tests at representative 1920x1080, 2560x1440, and 3840x2160 logical workspace sizes and supported scaling factors to verify required controls, keyboard access, accessible state, and a dominant 1440p video region.
- [x] 5.3 Add gated Windows integration coverage that generates tiny H.264/AAC MP4 and MOV fixtures in a temporary directory, or uses an explicit external fixture, for source loading, playback, seeking, current-time updates, backend diagnostics, and real errors without committing media.
- [x] 5.4 Measure and document on the reference Windows system that seek intent is reflected within 100 milliseconds, decoded target presentation is within 250 milliseconds at p95 for reference fixtures, and UI event-processing delay remains within 100 milliseconds at p95 during playback interaction.
- [x] 5.5 Verify long-source playback does not preload media, application memory does not grow with source duration, no decoded frames are retained in Python, and position updates retain only the latest required presentation state.

## 6. Compatibility and acceptance

- [ ] 6.1 Manually verify repeated seeks, long transcripts, transcript search during playback, candidate navigation, missing and unsupported sources, project switching, and clean close behavior on Windows.
- [x] 6.2 Verify GPU/CPU transcription selection and local Ollama clip detection remain functional and responsive while the embedded workspace is present, without changing their device, model, ranking, or persistence behavior.
- [ ] 6.3 Record the Qt multimedia backend and observable decode diagnostics on Windows, test concurrent playback with CUDA transcription and Ollama on the RTX 3070 Ti, and report contention or fallback without claiming unverified hardware decoding.
- [x] 6.4 Verify read-only local behavior creates no edited media and adds no trimming, exporting, captions, vertical rendering, publishing, Twitch integration, remote service, profile/account coupling, or playback persistence.
- [x] 6.5 Run pytest, Ruff lint, Ruff formatting check, Pyright, and strict OpenSpec validation, and resolve any failures before the feature is considered complete.
