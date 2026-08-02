## Purpose

Provide a responsive local video-review workspace that keeps supported source playback, transcript context, and ranked clip candidates synchronized inside BEEP.

## ADDED Requirements

### Requirement: Primary embedded video workspace
BEEP SHALL make the embedded video player the primary workspace while keeping the transcript panel, AI clip-candidate panel, playback controls, timeline, and active project indicator available in the same window.

#### Scenario: Active project has review data
- **WHEN** the user opens a project containing an available supported source and saved transcript or candidates
- **THEN** BEEP displays the source in the primary player and presents the project's transcript and candidates in the synchronized workspace

#### Scenario: No project is active
- **WHEN** BEEP starts without an active project
- **THEN** the workspace shows that no project is active and does not attempt to load media

### Requirement: Supported local playback
BEEP SHALL play compatible H.264/AAC MP4 and MOV files from the active project's local source path and SHALL NOT upload, stream, or otherwise transmit the source media.

#### Scenario: Supported MP4 is available
- **WHEN** the active project references an accessible compatible MP4 file
- **THEN** BEEP loads and plays the file inside the application

#### Scenario: Supported MOV is available
- **WHEN** the active project references an accessible compatible MOV file
- **THEN** BEEP loads and plays the file inside the application

#### Scenario: Container or codec cannot be played
- **WHEN** the selected MP4 or MOV cannot be decoded by the supported Windows playback backend
- **THEN** BEEP reports the real playback error without freezing, altering, or discarding project metadata, transcript segments, or clip candidates

#### Scenario: Project source is unavailable
- **WHEN** an opened project references a missing or inaccessible source file
- **THEN** BEEP keeps the saved transcript and candidates reviewable, shows the source as unavailable, and disables playback actions

### Requirement: Playback controls and time display
BEEP SHALL provide play, pause, and seek controls, a seekable timeline, and a current playback time display using the same media time base as transcript segments and clip candidates.

#### Scenario: Playback position changes
- **WHEN** media plays or a seek completes
- **THEN** BEEP updates the current time and timeline position to represent the player's current media position

#### Scenario: Timeline is activated
- **WHEN** the user activates a valid position on the timeline
- **THEN** BEEP seeks to the corresponding source timestamp

#### Scenario: Requested timestamp is outside the media range
- **WHEN** a requested timestamp is before zero or after the known media duration
- **THEN** BEEP clamps the request to the nearest valid media boundary and keeps the displayed time consistent with the effective seek position

### Requirement: Immediate non-blocking seeking
BEEP SHALL initiate every seek without blocking the PySide6 UI thread, acknowledge the requested timeline/time position within 100 milliseconds, and target presentation of the decoded frame within 250 milliseconds at p95 for supported local reference fixtures on the documented reference Windows system.

#### Scenario: User seeks while media is loaded
- **WHEN** the user requests any valid timestamp from the timeline, transcript, or candidate list
- **THEN** BEEP remains responsive, reflects the requested position immediately, and presents the closest decodable frame at that position as soon as the playback backend supplies it

#### Scenario: Backend seek takes longer than the target
- **WHEN** the playback backend cannot present the target frame within the seek-performance target
- **THEN** BEEP shows a seeking state, continues processing UI input, and reports the final effective position when the seek completes

### Requirement: Clip-candidate navigation
BEEP SHALL seek to an AI clip candidate's exact source-derived start timestamp when the user activates that candidate and SHALL preserve every candidate field and ranking value unchanged.

#### Scenario: Candidate is activated
- **WHEN** the user activates a displayed clip candidate while its project source is loaded
- **THEN** BEEP seeks playback to that candidate's start timestamp and keeps the candidate selected for review

#### Scenario: Candidate source is unavailable
- **WHEN** the user activates a candidate whose project source cannot be played
- **THEN** BEEP preserves the candidate selection and explanation, does not attempt a seek, and clearly explains why playback is unavailable

### Requirement: Transcript timestamp navigation
BEEP SHALL seek to a transcript segment's exact start timestamp when the user activates that segment's timestamp and SHALL preserve the segment's stored text, start time, and end time unchanged.

#### Scenario: Transcript timestamp is activated
- **WHEN** the user activates a timestamped transcript segment while its project source is loaded
- **THEN** BEEP seeks playback to the segment start and keeps that segment available for review

#### Scenario: Timestamp is activated without playable media
- **WHEN** the user activates a transcript timestamp while no supported source is loaded
- **THEN** BEEP leaves the transcript unchanged and clearly indicates that playback is unavailable

### Requirement: Playback synchronization
BEEP SHALL use current playback position to keep the timeline, current time, active transcript section, and applicable clip-candidate state synchronized without treating programmatic synchronization as a new user seek.

#### Scenario: Playback enters a transcript segment
- **WHEN** current playback time is within a transcript segment's start-inclusive and end-exclusive interval
- **THEN** BEEP highlights that segment as active without changing its text or timestamps

#### Scenario: Playback is between transcript segments
- **WHEN** current playback time is not within any stored transcript segment
- **THEN** BEEP clears the active transcript highlight while preserving search highlights and user selection

#### Scenario: Playback enters a candidate range
- **WHEN** current playback time is within one or more candidate ranges
- **THEN** BEEP indicates the highest-ranked matching candidate as active without changing candidate order or score

#### Scenario: Programmatic position update is displayed
- **WHEN** the player reports a new current position after playback or seeking
- **THEN** BEEP updates synchronized displays without recursively issuing another seek

### Requirement: Project lifecycle integration
BEEP SHALL bind playback only to the local media source resolved by the active project, release the previous source when projects change or the application closes, SHALL NOT let playback state alter stored project data, and SHALL NOT persist playback position in Version 1.

#### Scenario: User opens another project
- **WHEN** a different project becomes active
- **THEN** BEEP stops and releases the previous source before loading the new project's available supported source and restored review data

#### Scenario: Application restarts
- **WHEN** BEEP starts after a prior playback session
- **THEN** it shows recent projects without automatically reopening a project or restoring the previous playback position

#### Scenario: Playback state changes
- **WHEN** the user plays, pauses, seeks, or encounters a playback error
- **THEN** BEEP does not write that transient player state to the project or alter the project's media path, transcript, candidates, or metadata

#### Scenario: Existing processing features are used
- **WHEN** the user transcribes a project or runs local clip analysis from the video workspace
- **THEN** BEEP preserves the existing CUDA/CPU transcription selection, local Ollama analysis, project persistence, and actionable processing states

### Requirement: Responsive adaptive layout
BEEP SHALL keep playback and all workspace interactions responsive and SHALL present the video as the largest primary region at 2560 by 1440 while remaining usable without clipped controls at 1920 by 1080 and scaling cleanly at 3840 by 2160 under supported Windows display scaling.

#### Scenario: Workspace is shown at 1440p
- **WHEN** BEEP is displayed at 2560 by 1440 with supported Windows scaling
- **THEN** the video remains the dominant region and the transcript, candidates, controls, timeline, status, and active project indicator remain simultaneously usable

#### Scenario: Workspace is shown at 1080p
- **WHEN** BEEP is displayed at 1920 by 1080 with supported Windows scaling
- **THEN** panels remain scrollable or resizable and no required playback or review control is clipped

#### Scenario: Workspace is shown at 4K
- **WHEN** BEEP is displayed at 3840 by 2160 with supported Windows scaling
- **THEN** controls and text scale legibly without leaving the player or review panels at fixed low-resolution dimensions

#### Scenario: Playback continues during UI interaction
- **WHEN** the user scrolls, searches, selects transcript content, or reviews candidate details during playback
- **THEN** playback and UI input continue without a repeatable UI event-processing delay above 100 milliseconds at p95 on the documented reference system

### Requirement: Bounded playback resource use
BEEP SHALL stream and decode local media without loading the complete source into application memory, SHALL keep application-controlled playback memory independent of source duration, and SHALL NOT retain decoded frame copies outside the active playback backend.

#### Scenario: Long source is loaded
- **WHEN** the user opens a supported multi-hour VOD
- **THEN** BEEP loads it for playback without reading the entire media file into memory or creating a duration-sized frame or timestamp cache

#### Scenario: Playback position updates frequently
- **WHEN** the backend emits position or frame updates faster than the interface needs to repaint
- **THEN** BEEP coalesces presentation work while retaining only the latest required playback state

#### Scenario: Project source changes
- **WHEN** the user opens another project or closes the application
- **THEN** BEEP releases references to the prior source and any application-owned playback resources

### Requirement: Accessible playback and review controls
BEEP SHALL expose playback, timeline, transcript activation, candidate activation, active project, seeking, and error states through keyboard-operable controls and accessible text or state, and SHALL NOT communicate required information through color alone.

#### Scenario: Keyboard-only review
- **WHEN** the user navigates the workspace without a pointing device
- **THEN** focus is visible and follows a logical order, and the user can operate playback, the timeline, transcript timestamps, and candidate navigation

#### Scenario: Assistive technology inspects playback
- **WHEN** a screen reader or other supported Windows accessibility client queries the workspace
- **THEN** controls expose meaningful names, roles, values, and current playback or error state

#### Scenario: Active transcript segment is highlighted
- **WHEN** playback activates a transcript segment
- **THEN** BEEP provides a non-color indication of the active segment while preserving legible contrast for active, selected, and search-match states

### Requirement: Version 1 playback boundary
The embedded video workspace SHALL remain local-only and SHALL NOT edit, trim, render, export, caption, vertically reframe, publish, download Twitch media, or modify original source files.

#### Scenario: User reviews a source
- **WHEN** the user plays, seeks, or navigates a supported project source
- **THEN** BEEP performs read-only local playback and creates no edited or exported media
