## Purpose

Turn a completed timestamped transcript into a local, explainable, ranked shortlist of moments that a streamer can review as potential clips.

## ADDED Requirements

### Requirement: Analysis eligibility
BEEP SHALL allow clip-candidate analysis only when the active project has a completed transcript containing at least one timestamped segment, and analysis SHALL begin only after an explicit user action.

#### Scenario: Completed transcript is available
- **WHEN** the active project has one or more completed transcript segments
- **THEN** BEEP enables the clip-analysis action

#### Scenario: Transcript is unavailable
- **WHEN** the active project has no completed transcript segments
- **THEN** BEEP keeps clip analysis unavailable and explains that transcription must finish first

### Requirement: Local-only processing
BEEP SHALL use Ollama as its sole AI inference runtime for candidate analysis. BEEP SHALL perform all inference locally, SHALL NOT send transcript text, video content, candidate data, or model prompts to a remote service, and SHALL NOT require a second AI SDK or runtime.

#### Scenario: Analysis runs
- **WHEN** the user starts clip analysis
- **THEN** Ollama performs the inference and all analysis inputs and outputs remain on the local PC

#### Scenario: Another AI provider is unavailable
- **WHEN** no remote AI service or additional AI SDK/runtime is configured
- **THEN** BEEP can still complete candidate analysis through local Ollama alone

### Requirement: Candidate time boundaries
BEEP SHALL derive every candidate's start and end timestamps from the source transcript segments, with the start preceding the end and both values remaining within the transcribed media duration.

#### Scenario: Candidate spans multiple segments
- **WHEN** related transcript segments form one candidate moment
- **THEN** BEEP uses the earliest included segment start and latest included segment end as the candidate boundaries

#### Scenario: Story requires setup and payoff
- **WHEN** a candidate's payoff depends on earlier setup for meaning or humor
- **THEN** BEEP includes the necessary setup through payoff in the candidate boundaries

#### Scenario: Setup and payoff cross adjacent analysis batches
- **WHEN** necessary setup appears at the end of one analysis batch and its payoff appears in the adjacent batch
- **THEN** BEEP preserves both in one candidate when overlapping context can recover the complete moment

#### Scenario: Full story context cannot be recovered
- **WHEN** BEEP cannot recover the necessary setup through payoff from the available transcript batches
- **THEN** BEEP down-ranks the candidate or clearly records the missing context in its weaknesses

#### Scenario: Invalid model boundaries are returned
- **WHEN** an analysis result contains reversed, missing, or out-of-range timestamps
- **THEN** BEEP rejects that result rather than displaying an invalid candidate

### Requirement: Explainable candidate output
BEEP SHALL provide a start timestamp, end timestamp, suggested clip type, score from 0 through 100, short summary, selection rationale, strong-signal list, and weakness-or-missing-context list for every candidate.

#### Scenario: Candidate is accepted
- **WHEN** a candidate passes validation
- **THEN** BEEP displays every required field without altering its source transcript timestamps

#### Scenario: Required candidate data is missing
- **WHEN** a candidate lacks any required field or has a score outside 0 through 100
- **THEN** BEEP rejects that candidate and continues handling other valid candidates

### Requirement: Positive-signal prioritization
BEEP SHALL raise candidate ranking when transcript evidence supports funny dialogue, deadpan humor, arguments, awkward moments, unexpected roleplay, story setup and payoff, or a moment understandable outside GTA RP.

#### Scenario: Strong standalone humorous moment
- **WHEN** a candidate contains a clear humorous setup and payoff that does not depend on GTA RP knowledge
- **THEN** BEEP records the relevant positive signals and ranks it above otherwise comparable candidates with weaker standalone context

#### Scenario: Multiple positive signals
- **WHEN** a candidate contains more than one supported positive signal
- **THEN** BEEP lists the distinct signals and reflects their combined strength in its score and rationale

### Requirement: Low-value-content down-ranking
BEEP SHALL lower candidate ranking when transcript evidence indicates music-only content, repetitive crafting, long dead air, driving without meaningful dialogue, or action lacking humor or understandable context.

#### Scenario: Meaningless or repetitive passage
- **WHEN** a candidate is dominated by a supported low-value signal and lacks a stronger positive signal
- **THEN** BEEP records the weakness and ranks the candidate below candidates with meaningful dialogue or payoff

#### Scenario: Positive and negative evidence coexist
- **WHEN** a candidate contains both strong positive evidence and a low-value passage
- **THEN** BEEP explains both and scores the candidate using the combined evidence rather than discarding either side

### Requirement: Honest visual-signal limitations
The transcript-first version of BEEP SHALL NOT claim it detected facial reactions, loading screens, menus, or other visual-only evidence, and SHALL identify unavailable visual context as a weakness when it could materially affect confidence.

#### Scenario: Dialogue suggests a visual reaction
- **WHEN** transcript context implies that a facial reaction may strengthen a candidate but no visual analysis occurred
- **THEN** BEEP reports the reaction as missing visual context rather than a detected positive signal

#### Scenario: Visual-only low-value content cannot be confirmed
- **WHEN** a candidate could overlap a menu or loading screen but transcript evidence cannot determine that fact
- **THEN** BEEP reports the uncertainty and does not claim the visual condition was detected

### Requirement: Ranked and deduplicated results
BEEP SHALL order accepted candidates by descending score and SHALL avoid presenting materially overlapping candidates that describe the same moment as separate results.

#### Scenario: Candidates have different scores
- **WHEN** analysis produces multiple valid candidates
- **THEN** BEEP presents the highest-scoring candidate first and the remaining candidates in descending score order

#### Scenario: Candidates substantially overlap
- **WHEN** two candidates represent the same transcript moment with materially overlapping boundaries
- **THEN** BEEP keeps the stronger candidate and excludes the duplicate from the ranked list

### Requirement: Responsive analysis and failure recovery
BEEP SHALL run analysis outside the PySide6 UI thread, show an in-progress state, and restore an actionable UI state after success or failure without changing the completed transcript.

#### Scenario: Analysis is running
- **WHEN** local candidate analysis takes time to complete
- **THEN** the window remains responsive and displays analysis progress or an indeterminate processing state

#### Scenario: Local model is unavailable or returns unusable output
- **WHEN** analysis cannot start or no valid structured result can be produced
- **THEN** BEEP shows a clear local setup or analysis error, preserves the transcript, and allows the user to retry

### Requirement: In-memory result lifecycle
Version 1 of BEEP SHALL keep generated clip candidates in application memory only and SHALL NOT create candidate database tables or restore candidates after restart.

#### Scenario: Valid candidates are generated
- **WHEN** analysis completes successfully
- **THEN** BEEP displays the ranked candidates for the current application session without writing them to SQLite

#### Scenario: Application restarts
- **WHEN** the user closes and reopens BEEP
- **THEN** previously generated candidate results are not restored and the completed transcript can be analyzed again
