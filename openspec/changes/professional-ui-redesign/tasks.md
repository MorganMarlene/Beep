## 1. Regression Baseline

- [x] 1.1 Add focused Qt tests that capture current project, processing, playback, transcript-search, candidate-selection, progress, and accessible-state behavior before presentation changes
- [x] 1.2 Add a resize regression test proving existing stateful widget instances and their values survive presentation density changes

## 2. Visual Foundation and Branding

- [x] 2.1 Create a small presentation theme module with an 8-logical-pixel spacing scale, exactly three semantic typography levels, dark-surface, blue, pink, neutral, state, radius, focus, scrollbar, and 150-250 millisecond motion tokens using no new dependency
- [x] 2.2 Implement the scalable Qt-painted blue-to-pink BEEP wordmark with no white in the wordmark, an accessible text identity, and a plain-text fallback
- [x] 2.3 Redesign the header around the wordmark and existing active-project context without adding an action or changing project behavior
- [x] 2.4 Add automated tests for required foreground/background contrast pairs, 8-point spacing values, exactly three typography roles, and the wordmark's text, gradient endpoints, and scaling behavior
- [x] 2.5 Implement lightweight 150-250 millisecond presentation transitions for eligible hover, focus, selection, status, and empty-to-content states without animating application state, video, timeline position, or splitter drag
- [x] 2.6 Add tests for animation duration bounds, immediate underlying state changes, reduced-motion fallback, completion cleanup, and coalescing or omission of rapid repeated updates

## 3. Responsive Creator Layout

- [x] 3.1 Implement named expanded and compact density rules based on available logical workspace width rather than raw monitor resolution
- [x] 3.2 Rebalance the workspace so expanded mode keeps the sidebar at 240-288 logical pixels and at most 14 percent of window width, the header at most 96 logical pixels high, and the player-side pane at least 60 percent of non-sidebar width by default
- [x] 3.3 Adapt margins, spacing, widths, splitter proportions, and supporting-panel orientation in place without recreating playback, transcript, candidate, search, progress, or project widgets
- [x] 3.4 Add representative responsive geometry tests for 1920x1080, 2560x1440, and 3840x2160 logical workspaces, including the expanded sizing contract, compact future-region collapse, required-control visibility, and positive usable panel sizes

## 4. Workflow Navigation and Review Hierarchy

- [x] 4.1 Redesign the sidebar and header to distinguish Projects, Processing, Review, active project context, and the bounded future utility region while retaining the current New Project, Open Project, recent-project, Open Video, Transcribe, CPU fallback, and Analyze Clips behavior
- [x] 4.2 Add visually subordinate, non-interactive future-area labels for Publishing, folders, profiles, queues, notifications, and approved space-reservation examples, mark them as future, and exclude them from focus and activation
- [x] 4.3 Reserve a stable visual location for a future primary Process VOD action without creating the button, combining current operations, or adding workflow coordination
- [x] 4.4 Provide collapsing presentation insertion points so Projects can later accept a folder tree, the header can later accept a profile selector and notifications, Processing can later accept a queue, and Publishing can later accept destinations without adding their models, controllers, persistence, or enabled controls
- [x] 4.5 Increase the player region and simplify its surrounding chrome without replacing the playback surface, adapter, clock, controls, timeline, or signal connections
- [x] 4.6 Improve transcript Body-level typography, 8-point spacing, scrollbar, timestamp affordance, and overlapping active, selected, and search-match treatments without changing stored or rendered transcript content
- [x] 4.7 Improve candidate list and detail hierarchy for rank, score, type, time range, summary, reasoning, signals, and weaknesses without changing candidate values, order, selection, or seek behavior

## 5. Component and State Polish

- [x] 5.1 Apply consistent primary, secondary, quiet, focused, selected, and disabled button and card treatments while preserving every existing enablement rule
- [x] 5.2 Redesign progress, loading, seeking, success, warning, and error presentation around the existing status values and update signals while ensuring decorative transitions never queue on rapid updates, add idle timers, or block work
- [x] 5.3 Add concise empty states for no project, no VOD, no transcript, no search matches, no candidates, and unavailable playback using only existing actions
- [x] 5.4 Verify that color is never the sole state indicator and that real existing diagnostics, device, model, timing, CUDA source, and playback-backend text remain available

## 6. Accessibility and Behavior Preservation

- [x] 6.1 Verify logical keyboard focus order and visible focus across project, processing, playback, transcript-search, transcript-seeking, and candidate-review controls
- [x] 6.2 Verify accessible names, roles, values, and descriptions for the wordmark, active project, progress, loading, playback, transcript, candidates, and errors
- [x] 6.3 Add regression tests confirming the redesign does not change project persistence, database schema, media handling, playback, transcription, AI analysis, search, selection, or action outcomes
- [x] 6.4 Verify future labels and insertion points have no click handler, focus policy, state mutation, domain dependency, fixed compact-mode space claim, or misleading enabled-control styling
- [x] 6.5 Measure presentation transitions and confirm they do not regress the embedded workspace's existing input and playback responsiveness targets

## 7. Windows Visual Acceptance and Validation

- [ ] 7.1 Document and run manual visual checks at physical 1920x1080, 2560x1440, and 3840x2160 for premium creative-software cohesion, hierarchy, 8-point alignment, three-level typography, future-region capacity, clipping, resizability, readability, scrollbars, progress, empty states, and video dominance
- [ ] 7.2 Verify Windows display scaling at 100%, 125%, 150%, and 200% where supported, including movement between differently scaled monitors, compact future-region collapse, and crisp wordmark rendering
- [ ] 7.3 Manually exercise keyboard-only project, processing, playback, transcript, and candidate review plus Windows accessibility inspection and reduced-motion behavior
- [ ] 7.4 Run the existing playback, transcription, Ollama, Projects, and transcript-search manual smoke paths and confirm presentation changes preserve their behavior
- [x] 7.5 Run pytest, Ruff lint, Ruff formatting check, Pyright, and strict OpenSpec validation, and do not commit if any required check fails
