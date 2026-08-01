## Why

BEEP currently ends its workflow at a searchable transcript, leaving streamers to review long VODs manually for moments worth clipping. A small local ranking pass can turn that transcript into an explainable shortlist while keeping source media and creator data on the user's PC.

## What Changes

- Add an explicit, user-started analysis step after transcription completes.
- Analyze timestamped transcript segments locally and combine nearby segments into bounded clip candidates.
- Rank candidates using positive signals such as funny or deadpan dialogue, arguments, awkward moments, unexpected roleplay, story setup/payoff, and context that can work outside GTA RP.
- Down-rank transcript evidence of music-only passages, repetitive activity, dead air, context-free action, and driving without meaningful dialogue.
- Return each candidate's start and end timestamps, suggested clip type, score, short summary, selection rationale, strong signals, and weaknesses or missing context.
- Present a ranked candidate list without cutting, rendering, exporting, or publishing video.
- Treat facial reactions, menus, loading screens, and other visual-only evidence as unavailable in the transcript-first version; BEEP must identify that limitation rather than invent visual signals.
- Use Ollama as the sole AI inference runtime, with no remote AI service or second AI SDK/runtime.
- Keep Version 1 results in memory only; candidate persistence and restart restoration are deferred to a separate future change.
- Keep analysis local, asynchronous, and small enough for a single Windows desktop workflow.

## Capabilities

### New Capabilities

- `clip-candidate-ranking`: Generate, explain, and rank local clip candidates from a completed timestamped transcript.

### Modified Capabilities

None.

## Impact

- Adds a local analysis boundary, typed in-memory clip-candidate data, and a minimal ranked-results view.
- Extends the existing post-transcription workflow without changing transcription output or the SQLite data model.
- Requires Ollama and one documented small Ollama model suitable for the target Windows PC; no other AI dependency is introduced.
- Adds background execution, validation, and tests for narrative boundaries, ranking, structured output, and UI state.
- Does not add candidate persistence, restart restoration, video editing, playback, visual analysis, cloud services, scheduling, or publishing.
