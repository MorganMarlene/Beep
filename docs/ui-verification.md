# Professional UI Verification

This checklist covers the presentation-only Professional UI Redesign. It does not
change or replace the existing functional verification for playback,
transcription, Ollama clip analysis, or Projects.

## Automated and rendered verification

| Workspace | Density | Verified presentation behavior |
| --- | --- | --- |
| 1920 x 1080 | Compact | Future-capacity labels collapse, all current controls remain visible, candidate content stacks for a readable measure, and the video remains dominant. |
| 2560 x 1440 | Expanded | Sidebar stays bounded, the player-side pane uses at least 60% of the non-sidebar width, future-capacity regions appear, and transcript and candidate review remain readable. |
| 3840 x 2160 | Expanded | Header and sidebar remain bounded rather than scaling without limit, and stateful review widgets survive the resize unchanged. |

The 1920 x 1080 and 2560 x 1440 layouts were rendered with Qt's offscreen
platform and visually reviewed after implementation. The refinement pass changed
the compact candidate panel from a narrow side-by-side arrangement to a vertical
list-and-detail arrangement. Automated tests cover the three logical workspace
sizes, widget identity and state retention, non-interactive future regions,
keyboard focus order, contrast, typography roles, spacing tokens, motion cleanup,
and the 100 ms p95 responsive-layout target.

## Windows accessibility behavior

- The BEEP wordmark is painted locally with a blue-to-pink gradient and retains an
  accessible text name.
- Current controls have accessible names and a logical keyboard focus order.
- Focus styling is visible without relying on color alone; statuses include text
  labels and preserve their full diagnostic messages.
- Decorative transitions are bounded to 150-250 ms, never animate playback or
  application state, and are disabled when Windows client-area animations are
  disabled.
- `BEEP_REDUCED_MOTION=1` forces the reduced-motion path for verification or for a
  user who needs an explicit local override.

## Physical Windows acceptance checklist

Complete this checklist on release-target hardware before merging or packaging:

1. Inspect 1920 x 1080, 2560 x 1440, and 3840 x 2160 displays for clipping,
   readable text, video dominance, card alignment, scrollbar usability, and empty,
   loading, progress, success, and error states.
2. Verify 100%, 125%, 150%, and 200% Windows display scaling, including moving the
   window between monitors with different scale factors.
3. Confirm the gradient wordmark remains crisp and the compact layout activates
   when logical workspace width is constrained.
4. Exercise the complete interface with the keyboard and inspect names, roles,
   values, and descriptions with a Windows accessibility inspector.
5. Disable Windows animation effects and confirm content appears immediately with
   no decorative fades.
6. Run local playback with audio, transcription on CUDA and CPU, Ollama analysis,
   project save/reopen, transcript search, timestamp seeking, and candidate seeking
   to confirm the presentation layer did not alter behavior.

Physical multi-monitor and assistive-technology checks cannot be represented by
offscreen automated tests; this checklist keeps those release checks explicit.
