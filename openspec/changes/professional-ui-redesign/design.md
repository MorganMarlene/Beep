## Context

See `proposal.md` for motivation. The main PySide6 window currently builds its header, fixed-width sidebar, video-first splitter workspace, transcript and candidate cards, and bottom status area in `SpotlightWindow`. `VideoWorkspace` owns the player surface and review-panel splitters. Existing widgets already carry application state, signal connections, accessible names, and behavior that must survive the redesign unchanged.

The interface uses one dark Qt stylesheet and code-built widgets. The redesign must remain local, use only PySide6 and local resources, avoid database or service changes, and coexist with the in-progress embedded-video-workspace behavior. Qt layout dimensions are device-independent pixels, so physical screen resolution alone is not a safe layout breakpoint under Windows display scaling.

## Goals / Non-Goals

**Goals:**

- Establish a maintainable visual system for color, typography, spacing, radii, focus, and component states.
- Make the video the dominant 1440p workspace while preserving practical transcript and candidate review.
- Adapt layout density from available window width without destroying or recreating stateful widgets.
- Reserve presentation-level extension zones for folders, profiles, publishing, processing queues, and notifications without implementing their domain behavior.
- Preserve existing signal wiring, accessible semantics, enablement rules, and runtime performance.
- Make current workflow areas obvious and future areas unmistakably unavailable.

**Non-Goals:**

- Reworking application coordination, playback, persistence, transcription, Ollama analysis, or background execution.
- Adding navigation routing, a Process VOD coordinator, new project concepts, or any future workflow represented by the design.
- Introducing a web UI, QML migration, external theme package, bundled font, or remote design asset.
- Persisting layout, splitter, navigation, or presentation preferences.

## Decisions

### 1. Centralize presentation tokens without creating a UI framework

Create one small presentation-focused theme module containing named colors, type roles, spacing increments, radii, motion durations, and the generated Qt stylesheet. Widget object names or dynamic properties will select component variants such as primary, secondary, quiet, selected, warning, and error. The theme will be applied once at the window or application boundary.

This is preferred over continuing to expand an undifferentiated stylesheet inside `app.py`, because the redesign needs consistent values across the main window and video workspace. A third-party theming package is rejected because it adds a dependency without improving the current behavior. A broad reusable design-system framework is also rejected as premature.

The palette will use near-black surfaces, restrained elevated surfaces, blue and pink accents, and neutral text colors selected against their actual backgrounds. Pink and blue remain accents rather than large reading surfaces. Borders will be reserved for focus, selection, separation that spacing cannot provide, and error emphasis. A premium creative-software result is defined by coherent surface elevation, aligned content edges, disciplined accent use, polished states, and the absence of raw default-looking controls or unrelated card treatments across the populated workspace.

Spacing uses an 8-logical-pixel base with named tokens such as 8, 16, 24, 32, and 40. A 4-pixel half-step is restricted to optical adjustments and dense internal separation; primary margins, gaps, padding, and control dimensions remain on the 8-point rhythm. Compact mode selects smaller tokens from the same scale instead of inventing a second scale.

Typography exposes exactly three semantic levels:

- Display: BEEP identity and primary workspace or project context.
- Section: sidebar groups, workspace regions, and panel headings.
- Body: controls, transcript, candidates, metadata, timestamps, statuses, captions, and helper text.

Body variants may change weight, color, capitalization, line height, or numeric font features, but do not introduce a fourth size role. This gives enough hierarchy for a desktop creator tool without the fragmented text sizing common in dashboard-style layouts.

### 2. Render the gradient wordmark as a local vector-like Qt control

Use a small presentation-only widget that paints the text `BEEP` with `QPainter` and a horizontal `QLinearGradient` from bright blue to bright pink. It will use the Windows UI typeface stack available through Qt, scale from logical font metrics, expose `BEEP` as its accessible name, and provide a plain-text fallback if custom painting is unavailable.

This avoids a low-resolution bitmap and requires no new asset pipeline. Splitting the wordmark across separately colored labels is rejected because it does not produce the requested continuous gradient. A bundled SVG is viable but rejected for Version 1 because the code-rendered treatment is simpler to scale, theme, test, and package.

### 3. Use available-width density modes, not physical-resolution detection

The main window will derive an expanded or compact presentation from the central workspace's available logical width. It will not branch on a monitor's raw pixel resolution or manually multiply sizes by device pixel ratio. Qt's high-DPI behavior remains authoritative.

- Expanded mode targets the usable width typical of a maximized 2560x1440 workspace: a 240-to-288 logical-pixel navigation rail capped at 14 percent of the window, a header capped at 96 logical pixels, a player-side pane receiving at least 60 percent of non-sidebar width by default, and a review column that keeps transcript and candidate context useful.
- Compact mode targets 1920x1080 and narrower supported windows: smaller margins and navigation width, wrapped or stacked supporting controls, and scrollable/resizable review regions with no hidden required action.
- 4K uses expanded composition with Qt-scaled typography and spacing; maximum widths prevent navigation, header, status, and future-capacity chrome from consuming the additional workspace so growth primarily benefits video and review content.

Mode changes will adjust margins, spacing, width constraints, splitter ratios, and orientation of supporting review splits where necessary. Existing stateful widgets will be retained and re-laid out rather than reconstructed, so playback, search, selection, progress, and project state are not reset. Breakpoints and ratios will be named constants verified by geometry tests, not scattered magic numbers.

### 4. Keep the existing video-first workspace and refine its information architecture

The player remains the primary pane and continues using the existing playback adapter and central clock. The workspace will reduce decorative card chrome around the video, keep playback controls immediately beneath it, and move low-frequency video metadata into a compact supporting section. The player and playback surface will never be restyled or recreated in response to playback position updates.

The review pane remains independently resizable. Transcript presentation will allocate more line height, distinguish timestamp affordances from dialogue, preserve search and active highlights, and retain the same underlying document. Candidate presentation will give rank, score, type, time range, and summary a scan-friendly hierarchy while keeping all reasoning, signals, and weaknesses reachable. No candidate content is rewritten or suppressed.

Replacing Qt Multimedia, changing the clock model, or adding a custom timeline is rejected because those are playback changes. Adding tabs that hide transcript or candidates by default at 1440p is rejected because simultaneous review is part of the current workspace contract.

### 5. Express the creator workflow through grouping, not new routing

The sidebar and header will visually distinguish:

- Projects: active project, New Project, Open Project, and recent projects.
- Processing: the existing Open Video, Transcribe, CPU fallback, and Analyze Clips controls, presented in their current enabled states.
- Review: the active video, transcript, search, and candidate workspace.
- Future Publishing: a subordinate, non-interactive label explicitly marked as future functionality.

The current composition uses presentation containers with narrowly defined future capacity:

- The Projects region can later replace or augment its flat recent-project list with a folder tree without moving persistence logic into the sidebar.
- The header separates brand, active project context, and a bounded utility zone that can later accept an independent profile selector and notification entry point.
- The Processing region keeps a consistent primary-action location that could later host an approved Process VOD command and a bounded subordinate region that could later present a processing queue.
- The future Publishing region can later accept destination navigation without displacing current Projects or Review content.

These are layout insertion points, not domain interfaces or empty fixed-size panels. At compact density they collapse before current controls or review content. Version 1 will not create folder behavior, profiles, publishing destinations, a queue, notifications, a Process VOD button, or orchestration. Scheduling, Twitch import, and mobile sync may be represented only as non-focusable future labels if needed to demonstrate spatial capacity; they will not resemble enabled controls.

A new navigation controller is rejected because there are no approved destinations to route to. Disabled `QPushButton` placeholders are also rejected because they add confusing controls and keyboard/accessibility noise; semantic labels with a clear future marker are sufficient.

### 6. Treat progress, status, loading, and empty states as one visual language

The status area will remain the source of truth for progress text, progress value, device, model, timing, CUDA source, playback backend, and errors. Presentation may compact idle diagnostics and elevate the active operation, but values and update timing remain unchanged. State visuals will pair color with labels, icons drawn by Qt where useful, progress values, or shape changes.

Empty-state copy will be concise and tied only to approved actions. The main empty project state points to New Project or Open Project; media, transcript, candidates, search, and playback each explain their current absence. No empty state markets or launches deferred functionality.

Progress animation will use the existing `QProgressBar` and Qt state changes. New timers, animated background effects, or repeated stylesheet re-polishing are rejected because they can compete with playback and processing UI updates.

### 7. Use bounded motion without coupling animation to application state

Eligible hover, focus, selection-emphasis, status-entry, and empty-to-content transitions use one of a small set of tokenized durations between 150 and 250 milliseconds, with approximately 180 milliseconds as the normal default. The underlying enabled, selected, visible, or content state changes immediately; animation only interpolates its presentation.

Animations use lightweight Qt property or value animation on presentation-owned opacity or accent values. They never animate the video surface, timeline position, splitter geometry during user drag, long-running indeterminate effects, or stylesheet regeneration. Rapid playback, progress, and diagnostic updates bypass or coalesce decorative transitions rather than enqueueing animations. No animation object is retained after completion, and idle UI has no animation timer.

When the supported Windows or Qt environment disables animation or communicates a reduced-motion preference, the same state transition completes immediately. This is preferred over an application-specific motion setting because the change does not approve new configuration or persistence. Large layout motion, spring physics, continuous gradients, and third-party animation frameworks are rejected for performance and accessibility reasons.

### 8. Preserve and verify accessibility as part of the visual implementation

Existing accessible names and descriptions remain attached to the same semantic controls. New decorative frames and future labels will not enter the focus chain. The gradient wordmark exposes text independently of its paint. Focus indicators use both a high-contrast outline and geometry, and active/search/selection states use more than hue alone.

Palette contrast will be calculated in tests for defined foreground/background token pairs. Keyboard-focused tests will verify current actions remain reachable and future labels are not focusable. Manual Windows verification will include 100%, 125%, 150%, and 200% scaling where the available displays support them, plus keyboard-only review and Windows accessibility inspection.

### 9. Verify responsive behavior without brittle full-image snapshots

Automated Qt tests will instantiate the window offscreen at representative logical workspace sizes and assert required controls are visible, geometry remains within the central window, splitter regions retain positive usable sizes, future labels are non-interactive, and resizing preserves stateful widget identity and values. Theme tests will verify required token contrast, 8-point spacing values, the three typography roles, motion-duration bounds, and wordmark gradient endpoints.

Existing behavior tests remain the primary regression protection. A small manual visual checklist at physical 1920x1080, 2560x1440, and 3840x2160 will cover hierarchy, truncation, scrollbars, mixed-DPI movement, and video playback because pixel-perfect screenshots are brittle across Qt and Windows rendering versions.

## Risks / Trade-offs

- **[Risk] `SpotlightWindow` already owns substantial presentation and workflow wiring, so large inline layout edits could increase coupling.** → Extract only current presentation helpers and theme values while leaving workflow slots and domain state in place; split further only where the redesign directly needs it.
- **[Risk] Responsive re-layout can accidentally recreate widgets and lose playback or selection state.** → Retain widget instances, change layout constraints or splitter orientation in place, and add identity/state-preservation tests around breakpoint changes.
- **[Risk] Qt styles can differ across Windows versions and multimedia backends.** → Style explicit semantic states, avoid assumptions about native control metrics, and run clean-machine manual checks on the supported Windows baseline.
- **[Risk] Future labels could be mistaken for promised or broken features.** → Mark them as future, render them visually subordinate, keep them non-focusable, and avoid button styling or click handlers.
- **[Risk] Larger text and spacing can reduce useful content at 1080p.** → Use compact density values below the logical-width threshold while retaining minimum readable type and allowing splitter resizing and scrolling.
- **[Risk] Frequent styling work could affect playback responsiveness.** → Apply static theme rules once, avoid stylesheet regeneration during clock updates, and retain the embedded workspace's existing responsiveness tests.
- **[Risk] Decorative animations could queue during rapid playback, progress, or selection updates.** → Limit motion to 150-250 milliseconds, coalesce or skip repeated transitions, retain no idle animation, honor reduced motion, and test that input and playback timing remain within existing responsiveness targets.
- **[Risk] Reserved future regions could waste space or create premature coupling.** → Use bounded presentation insertion points that collapse in compact mode and define no data model, service, controller, or enabled action.
- **[Trade-off] Code-rendered branding is less editable by non-developers than an external design asset.** → Keep the gradient endpoints and type metrics tokenized so a later approved brand-asset change remains localized.

## Migration Plan

1. Capture the current widget-state and responsive-behavior baseline in focused tests.
2. Add the 8-point spacing, three-level typography, palette, motion tokens, and gradient wordmark, then replace the existing header styling.
3. Refine the sidebar, header utility region, processing region, and workflow grouping using existing actions and non-interactive or empty collapsing future insertion points.
4. Adapt the video, transcript, candidate, and status compositions without changing their data or signal connections.
5. Add empty-state, component-state, and bounded 150-250 millisecond presentation transitions, then verify accessibility, reduced motion, contrast, and performance.
6. Run automated validation and the documented 1080p, 1440p, 4K, mixed-DPI, keyboard, playback, processing, and project-restoration checks.

There is no database, media, model, or configuration migration. Rollback consists of reverting the presentation commit; existing projects and application data remain compatible.
