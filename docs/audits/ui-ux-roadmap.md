# UI and UX Roadmap

## Current UI assessment

### Verified strengths

- The UI has a coherent dark theme with blue/pink accents, clear header/sidebar/content/status regions, readable transcript and candidate panes, and scrollable result lists.
- `SpotlightWindow` uses a 960×700 minimum and 1180×820 initial size; the main content stretches while the sidebar stays fixed at 210 px.
- Long-running probe, transcription, and analysis work is launched through Qt's thread pool, keeping the event loop available in normal expected-error paths.
- Control availability prevents common invalid actions, and missing media restores transcript/candidates while disabling media-dependent actions.
- Transcript search is case-insensitive, highlights matching segments, reports counts, wraps navigation, and scrolls to the selected result.

### Findings

| Severity | Classification | Finding | Recommendation |
|---|---|---|---|
| High | Verified | All current/future view state is concentrated in `SpotlightWindow`; adding playback/timeline/publishing here will become difficult to reason about and test. | Split view components after the job-state boundary and before timeline work. |
| High | Verified | Unexpected worker exceptions can leave controls disabled; no cancel/close policy exists. | Add one centralized operation-state model with cancel and terminal outcomes before one-click processing. |
| Medium | Verified | Fixed header height/sidebar width, point/pixel stylesheet sizes, fixed candidate minimum width, and stacked cards have not been tested at 1440p scaling, high DPI, localization, or large text. | Establish a responsive layout/visual test matrix; use splitters and size policies where user value is clear. |
| Medium | Verified | Qt 6 provides DPI scaling, but BEEP does not persist/clamp window geometry across mixed-DPI monitors or define a scale-rounding/test policy. | Test 100/125/150/200% and restore geometry only when it intersects an available screen. |
| Medium | Verified | No explicit accessible names/descriptions, label buddies, keyboard shortcuts, focus-order tests, screen-reader evidence, or high-contrast/system-theme behavior exists. | Add accessibility semantics and keyboard workflow before controls multiply. |
| Medium | Verified | Long diagnostics are put in a status label; users cannot reliably copy structured details, and progress has no cancel action. | Provide concise status plus expandable/copyable redacted detail in a dedicated change. |
| Low | Verified | Selection/highlight colors are hard-coded in `SpotlightWindow._apply_match_highlights`, separate from theme tokens. | Centralize semantic selection/error/success/focus tokens when the theme next changes. |

## 1440p-first UI checklist

Primary acceptance canvas: 2560×1440. Test at 100%, 125%, and 150% Windows scaling; also test 1920×1080 at 100/150%, 3840×2160 at 150/200%, and mixed-DPI monitor transitions.

- [ ] At 2560×1440/125%, project identity, video details, transcript, candidates, and status are usable without window maximization.
- [ ] No button, label, progress text, timestamp, candidate score, or error is clipped at 100/125/150%.
- [ ] Transcript and candidate review can each receive useful vertical space; panes are resizable when playback/timeline arrives.
- [ ] Sidebar stays legible but yields space on narrower windows; a future collapse behavior is specified rather than improvised.
- [ ] Text remains readable at Windows text-size settings up to the supported threshold; layouts reflow instead of overlapping.
- [ ] Minimum interactive target is at least 32×32 logical px for compact desktop controls, preferably 40×40 for primary actions.
- [ ] Focus indicators are visible against black, blue, and pink states; hover is never the only affordance.
- [ ] Status/device/model/timing values wrap or elide with a tooltip/copy path; long local paths and errors do not widen the window.
- [ ] Transcript/candidate timestamps use a stable-width readable font/column when timeline synchronization is added.
- [ ] Empty, loading, success, no-match, missing-media, offline-Ollama, CPU-fallback, and partial-result states are visually distinct by text/icon as well as color.
- [ ] Dragging between monitors with different scaling does not blur, resize incorrectly, or place dialogs off-screen.
- [ ] Restored geometry is clamped to current screens after disconnecting a monitor or changing resolution.
- [ ] Native file/OAuth dialogs appear on the active monitor and remain associated with the parent window.
- [ ] Screenshot/visual regression baselines cover primary states without embedding private VOD/transcript/account data.

## Accessibility checklist

- [ ] Every input has a visible label or accessible name; labels are buddies for their fields.
- [ ] Logical tab order covers sidebar, primary actions, search/navigation, transcript, candidate list/details, status, and cancel.
- [ ] All workflows are keyboard-only; define standard shortcuts such as Open, Find, next/previous match, play/pause, and cancel without conflicts.
- [ ] Screen readers announce application/window, active project, processing stage/progress, selected candidate, timestamps, errors, and completion without excessive chatter.
- [ ] Progress announcements are throttled and use an appropriate live/status mechanism.
- [ ] Color is not the sole signal for selected, error, disabled, device, or completion state.
- [ ] Text/background, focus, selection, disabled text, and accent combinations meet WCAG AA contrast targets where applicable; verify rendered colors rather than source hex alone.
- [ ] Windows High Contrast and reduced-animation preferences have a usable fallback; do not force the stylesheet over essential system accessibility colors without testing.
- [ ] Search results expose current/total position, not only aggregate count.
- [ ] Timeline controls have accessible names, values, increments, time announcements, and coarse/fine keyboard seeking.
- [ ] Captions have safe-area, size, contrast/background, and preview controls; automatic text is editable before export.

## UI architecture sequence

### Change 1 — operation state and diagnostics

Introduce a typed state for idle/probing/transcribing/analyzing/cancelling/succeeded/failed with one active operation ID. Centralize enabled controls, progress, short message, technical detail, cancel, and stale-result handling. No visual redesign is required.

### Change 2 — bounded view decomposition

Extract project/sidebar, source details, transcript/search, candidate review, and status widgets with typed signals/data setters. Keep orchestration outside widgets. Do not create a generic component framework.

### Change 3 — one-click Process UX

Show explicit stages, completed/skipped/failed states, retry from the safe boundary, overall cancel, and preserved prior durable results. Do not imply FFmpeg/model progress that cannot be measured.

### Change 4 — embedded playback

Specify backend choice, supported codecs, audio, errors, exact clock, and resource release. Playback must not block analysis and must handle a missing/moved source. No editing yet.

### Change 5 — shared time model and timeline scrubbing

Use one canonical media time base for player, transcript, candidates, and later captions. Define variable-frame-rate behavior, keyboard seek increments, precision, selection loops, and test tolerances.

### Change 6 — boundary review and export

Add in/out handles, numeric timestamps, setup/payoff context warning, undo/reset, and render progress/cancel. Preserve AI suggestion separately from user-edited boundaries.

### Change 7 — vertical/caption/reframe preview

Introduce a preview surface and safe areas in stages: fixed vertical layout, editable captions, then dynamic reframing with confidence/fallback. Preview and export must use the same render recipe.

### Change 8 — profiles/accounts/publishing

Profile switch and account selection must show immutable provider identity, authorization state, scopes, exact source/destination, and shared-link impact. Publishing always has a final review summary until unattended policy is separately approved.

## Playback and timeline quality goals

These are future acceptance goals, not current measurements:

- play/pause response ≤100 ms p95 for a local indexed 1080p source;
- scrub preview/update ≤150 ms p95 during ordinary seeking, with clear busy feedback for expensive seeks;
- displayed player/transcript/candidate time agreement within 100 ms, with frame-accurate rules defined for export;
- timeline interaction maintains UI event-loop p95 ≤100 ms;
- switching project releases file handles within 1 second and never prevents safe app exit;
- a 4-hour VOD timeline does not require all frame thumbnails in memory; thumbnails are bounded/cached outside SQLite.

## Multi-profile and account UX safeguards

- Persistent, unambiguous active profile and project context in the header/sidebar.
- Source account and each destination show provider icon/name plus verified external account name; display names are not internal IDs.
- Account linking ends with identity/scope confirmation; reauthorization/disconnect operates on one connection.
- Shared destinations visibly list linked profiles; disconnect warns about queued jobs.
- Automated jobs show policy origin, schedule/time zone, current stage, next retry, and pause/cancel.
- Emergency global pause is always reachable and distinct from deleting jobs.
- AI suggestions, user approvals, automated decisions, and published outcomes are visually distinguishable and auditable.

## UI release checklist

- [ ] 1440p-first, 1080p fallback, 4K, mixed-DPI, and multi-monitor checklist passes.
- [ ] Keyboard-only, screen-reader, focus, contrast, high-contrast, and large-text checks pass.
- [ ] Long paths, Unicode, long errors, 10 recent projects, 10,000 transcript segments, and 200 candidates remain usable.
- [ ] Every long operation has accurate stage text, cancel, terminal recovery, and no event-loop freeze.
- [ ] Missing media, offline dependencies, expired authorization, and partial network work have explicit recovery paths.
- [ ] Playback/timeline/caption/reframe preview and rendered output agree within specified tolerances.
- [ ] No user action can silently select another profile/account/destination or publish based solely on AI output.
