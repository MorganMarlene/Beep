## Purpose

Define a polished, accessible, and responsive creator interface for BEEP that improves visual hierarchy and review comfort without changing existing application behavior.

## ADDED Requirements

### Requirement: Premium BEEP visual identity
BEEP SHALL present a premium creative-software appearance across the complete application through a disciplined dark-surface hierarchy, precise alignment, restrained borders, consistent typography and spacing, polished operational states, and deliberate blue and pink accent use. The modern header SHALL contain a clean BEEP wordmark rendered with a blue-to-pink gradient. The wordmark itself SHALL contain no white, SHALL remain crisp under supported Windows display scaling, and SHALL have an accessible text identity independent of its color treatment.

#### Scenario: Branded header is displayed
- **WHEN** the main window is visible
- **THEN** the header presents the BEEP wordmark in a blue-to-pink gradient without white in the wordmark and keeps the active project context visually distinct from the brand

#### Scenario: Display scaling changes
- **WHEN** BEEP is shown at a supported Windows display scaling level on a 1080p, 1440p, or 4K display
- **THEN** the wordmark and header remain sharp, legible, and correctly aligned without substituting a low-resolution raster treatment

#### Scenario: Complete creator workspace is populated
- **WHEN** an active project has video, transcript, AI candidates, and status information
- **THEN** the header, sidebar, player, review panels, controls, and status presentation use one cohesive creative-software visual language without raw default-looking controls, inconsistent card treatments, or competing accent colors

### Requirement: 8-point spacing system
BEEP SHALL use an 8-logical-pixel base unit for layout spacing. Standard margins, padding, gaps, control heights, and major component dimensions SHALL use whole multiples of 8; use of a 4-logical-pixel half-step SHALL be limited to optical alignment or compact internal separation and SHALL NOT replace the 8-point rhythm for primary layout.

#### Scenario: Standard workspace components are measured
- **WHEN** header, sidebar, cards, controls, transcript rows, candidate rows, status content, and empty states are displayed
- **THEN** their primary margins, padding, gaps, and heights align to the 8-point spacing system

#### Scenario: Compact 1080p density is active
- **WHEN** BEEP uses its compact presentation at 1920 by 1080
- **THEN** it reduces spacing by selecting smaller 8-point-system tokens rather than introducing unrelated arbitrary values

### Requirement: Three-level typography system
BEEP SHALL use exactly three semantic typography levels: Display for the BEEP identity and primary workspace context, Section for navigation groups and panel headings, and Body for controls, transcript dialogue, candidate content, metadata, status, captions, and supporting text. Variants within a level SHALL be limited to weight, color, capitalization, line height, and optional tabular or monospace numerals and SHALL NOT create an ungoverned fourth text-size hierarchy.

#### Scenario: Workspace hierarchy is scanned
- **WHEN** the user views the header, navigation, player, transcript, candidates, and status area together
- **THEN** Display, Section, and Body typography communicate the information hierarchy consistently without ad hoc text sizes

#### Scenario: Dense metadata is displayed
- **WHEN** timestamps, codecs, device details, model information, or other supporting values are shown
- **THEN** those values remain within the Body level and use weight, color, or numeral styling rather than a fourth typography level

### Requirement: 1440p-first responsive creator workspace
BEEP SHALL prioritize a 2560 by 1440 workspace in which the video player is the dominant content region, the project navigation is subordinate to the workspace, and the transcript and AI candidate panels remain simultaneously useful. At expanded density, the sidebar SHALL remain between 240 and 288 logical pixels and no more than 14 percent of total window width, the header SHALL remain no more than 96 logical pixels high, and the player-side pane SHALL receive at least 60 percent of the non-sidebar workspace width by default. The same interface SHALL remain operable at 1920 by 1080 and scale cleanly at 3840 by 2160 under supported Windows display scaling.

#### Scenario: Workspace is displayed at 2560 by 1440
- **WHEN** the application is maximized on a 2560 by 1440 display
- **THEN** the video player occupies the largest primary region while Projects, Processing, transcript review, candidate review, playback controls, and status information remain available without crowding

#### Scenario: Workspace is displayed at 1920 by 1080
- **WHEN** the application is maximized on a 1920 by 1080 display
- **THEN** all existing actions remain reachable, required labels are not clipped, and transcript and candidate content remains accessible through resizing or scrolling

#### Scenario: Workspace is displayed at 3840 by 2160
- **WHEN** the application is maximized on a 3840 by 2160 display with supported Windows scaling
- **THEN** typography, controls, spacing, and panel proportions scale legibly, the sidebar and header remain bounded, and the additional space primarily benefits the video and review content instead of oversized navigation chrome

#### Scenario: User resizes the window
- **WHEN** the main window crosses a supported responsive layout threshold
- **THEN** the workspace adapts panel proportions without resetting playback, selection, search, progress, project, transcript, or candidate state

### Requirement: Creator-workflow hierarchy
BEEP SHALL visually distinguish Projects, Processing, and Review as the current creator workflow. Existing Open Video, Transcribe, and Analyze Clips actions SHALL remain separate operations, but their placement SHALL establish a clear processing sequence and reserve a stable primary-action area for a possible future Process VOD workflow without implementing that workflow.

#### Scenario: Project is ready for processing
- **WHEN** an active project and supported local VOD are available
- **THEN** the existing processing actions are presented in a clear hierarchy while retaining their current labels, enablement rules, and individual behavior

#### Scenario: Future Process VOD capability is absent
- **WHEN** the redesigned interface is used in Version 1
- **THEN** BEEP does not expose an enabled Process VOD action or combine the existing processing operations

### Requirement: Balanced review presentation
BEEP SHALL improve review readability through larger typography, deliberate spacing, reduced non-semantic borders, consistent card treatment, and clear content hierarchy. Transcript text and timestamps SHALL remain exact, and every AI candidate field and rank SHALL remain unchanged.

#### Scenario: User reviews a transcript
- **WHEN** timestamped transcript segments are displayed
- **THEN** timestamps, dialogue, active segment, search matches, and user selection remain distinguishable and readable without changing transcript text, order, or time boundaries

#### Scenario: User reviews AI candidates
- **WHEN** ranked AI clip candidates are displayed
- **THEN** rank, score, clip type, time range, summary, reasoning, strong signals, and weaknesses remain readable and unchanged, with the selected candidate visually distinct

#### Scenario: User reviews video and supporting context
- **WHEN** video, transcript, and candidate data are all available
- **THEN** the larger video region remains primary while neither supporting review panel is obscured or made unreachable

### Requirement: Consistent component hierarchy and operational states
BEEP SHALL use consistent visual treatments for primary, secondary, and disabled controls; cards; scrollbars; progress; loading; success; warning; and error states. Required state information SHALL use text or another non-color indicator in addition to color.

#### Scenario: Processing is active
- **WHEN** metadata probing, transcription, or clip analysis is running
- **THEN** BEEP presents a legible progress treatment, current operation text, and applicable progress value without changing the underlying work or blocking the interface

#### Scenario: Operation fails
- **WHEN** an existing operation reports an error
- **THEN** the real existing diagnostic remains readable in an error treatment and the interface does not rely on pink, blue, or any other color alone to communicate failure

#### Scenario: Control is unavailable
- **WHEN** an existing control is disabled by its current enablement rules
- **THEN** its unavailable state is visually clear while its label remains legible and its behavior remains unchanged

### Requirement: Informative empty states
BEEP SHALL provide concise, visually consistent empty states for no active project, no local VOD, no transcript, no search matches, no AI candidates, and unavailable playback. Empty states SHALL explain the current state without advertising or activating deferred features.

#### Scenario: Application starts without an active project
- **WHEN** BEEP starts and no project is active
- **THEN** the interface clearly directs the user to the existing New Project or Open Project actions and does not imply that processing or review data exists

#### Scenario: Review content is not yet available
- **WHEN** the active project has no transcript or AI candidates
- **THEN** the corresponding panel explains what is absent using only currently available actions

### Requirement: Explicit future-area boundary
BEEP SHALL reserve adaptable presentation regions for a future project folder tree, profile selector, Publishing destination navigation, processing queue, and notification entry point, as well as subordinate space for scheduling, Twitch import, and mobile sync. These regions SHALL be structural presentation capacity only: they SHALL NOT define domain interfaces, allocate persistent state, or reduce the current 1080p workspace through fixed empty panels. Every future area visibly represented in Version 1 SHALL be identified as future functionality, excluded from the keyboard activation path, and SHALL NOT create application state or invoke a workflow.

#### Scenario: Future Publishing is represented
- **WHEN** the navigation includes a future Publishing label or region
- **THEN** it is identified as unavailable future functionality and cannot be activated

#### Scenario: User navigates with the keyboard
- **WHEN** keyboard focus moves through the main interface
- **THEN** focus visits only current interactive controls and skips all future-area labels or placeholders

#### Scenario: Future extension capacity is reviewed at 1440p
- **WHEN** the expanded layout is inspected for future compatibility
- **THEN** the Projects region can later accept a folder hierarchy, the header can later accept an independent profile selector and notification entry point, the Processing region can later accept a queue, and the future Publishing region can later accept destinations without replacing the video player or redesigning project persistence

#### Scenario: Future extension capacity is shown at 1080p
- **WHEN** the compact layout is active
- **THEN** future labels or reserved containers collapse before any current action or review content is clipped or made unreachable

### Requirement: Restrained UI motion
BEEP SHALL use subtle 150-to-250-millisecond animations for eligible presentation-only transitions such as hover, focus, selection emphasis, status appearance, and empty-to-content changes. Animations SHALL NOT delay input, block the UI thread, animate the video surface or timeline clock, continuously consume resources while idle, or change application state. BEEP SHALL disable or reduce nonessential animation when the supported Windows or Qt environment indicates reduced motion or animations are unavailable.

#### Scenario: Eligible visual state changes
- **WHEN** an eligible control, selection, status, or content state changes and motion is permitted
- **THEN** the visual transition completes in no less than 150 milliseconds and no more than 250 milliseconds while the underlying state changes immediately

#### Scenario: Playback or processing updates rapidly
- **WHEN** playback position, progress, or diagnostics update repeatedly
- **THEN** BEEP coalesces or omits decorative animation so playback, processing feedback, and user input remain responsive

#### Scenario: Reduced motion is active
- **WHEN** the supported environment requests reduced motion or disables animations
- **THEN** BEEP presents the final state immediately without losing information, focus visibility, or hierarchy

### Requirement: Performance-neutral presentation
The redesigned presentation SHALL preserve the embedded workspace's existing responsiveness target of no repeatable UI event-processing delay above 100 milliseconds at p95 on the documented reference system. Responsive layout changes SHALL complete without recreating stateful widgets, completed animations SHALL release their resources, and the idle interface SHALL run no continuous decorative animation.

#### Scenario: User reviews content during playback
- **WHEN** playback continues while the user scrolls, searches, changes selection, or receives a status update
- **THEN** presentation styling and eligible animations do not cause a repeatable UI event-processing delay above 100 milliseconds at p95

#### Scenario: Responsive density changes
- **WHEN** the window crosses a compact or expanded threshold
- **THEN** BEEP updates layout presentation without blocking input, interrupting playback, or rebuilding the player, transcript, candidate, project, or progress widgets

#### Scenario: Interface is idle
- **WHEN** no operation or user transition is active
- **THEN** no decorative animation timer or queued presentation transition continues running

### Requirement: Accessible professional interface
BEEP SHALL preserve meaningful accessible names, roles, values, descriptions, logical focus order, keyboard operation, and visible focus across the redesigned interface. Normal text SHALL target a contrast ratio of at least 4.5 to 1, large text and essential graphical controls SHALL target at least 3 to 1, and no required meaning SHALL depend on color alone.

#### Scenario: Keyboard-only creator workflow
- **WHEN** a user operates BEEP without a pointing device
- **THEN** every existing project, processing, playback, transcript-search, transcript-seeking, and candidate-review action remains reachable in a logical order with a visible focus indicator

#### Scenario: Assistive technology examines the workspace
- **WHEN** a supported Windows accessibility client inspects the interface
- **THEN** current controls, progress, loading, active project, playback, transcript, candidate, and error states expose meaningful accessible information

#### Scenario: Multiple highlight states overlap
- **WHEN** a transcript segment or candidate is active, selected, or matched by search
- **THEN** each applicable state remains distinguishable through more than color while preserving legible contrast

### Requirement: Presentation-only redesign boundary
The redesign SHALL NOT change project data, database schemas, persistence, video playback, media handling, transcription, AI prompts or ranking, worker execution, search behavior, selection behavior, or any existing action's outcome. It SHALL NOT implement folders, reusable profiles, publishing destinations, processing queues, notifications, scheduling, Twitch import, mobile sync, editing, exporting, captions, or a Process VOD workflow.

#### Scenario: Existing workflow is exercised after redesign
- **WHEN** the user creates or opens a project, opens a VOD, plays or seeks it, transcribes it, searches the transcript, or analyzes candidates
- **THEN** the operation produces the same application state and data outcome as before the redesign

#### Scenario: Application data is inspected after redesign
- **WHEN** BEEP uses an existing project database
- **THEN** no migration or presentation-specific data write is required
