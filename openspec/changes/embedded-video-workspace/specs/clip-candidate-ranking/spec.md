## MODIFIED Requirements

### Requirement: Explainable candidate output
BEEP SHALL provide a start timestamp, end timestamp, suggested clip type, score from 0 through 100, short summary, selection rationale, strong-signal list, and weakness-or-missing-context list for every candidate. Every displayed generated field SHALL be English, every factual summary claim SHALL be supported by exact evidence within the selected transcript range, and missing context SHALL be stated explicitly.

#### Scenario: Candidate is accepted
- **WHEN** a candidate passes validation
- **THEN** BEEP displays every required field in English without altering its source transcript timestamps and builds its summary and rationale from validated transcript evidence and fixed English signal labels

#### Scenario: Model returns an unsupported claim
- **WHEN** a model candidate has no exact evidence quote within its selected transcript range
- **THEN** BEEP rejects that candidate instead of displaying speculative or invented information

#### Scenario: Required candidate data is missing
- **WHEN** a candidate lacks any required field, exact transcript evidence, an allowed positive signal, or a score from 0 through 100
- **THEN** BEEP rejects that candidate and continues handling other valid candidates

#### Scenario: Context is incomplete
- **WHEN** setup, payoff, visual context, or gameplay context needed to interpret a candidate is unavailable from the transcript
- **THEN** BEEP states the missing context through an English weakness label and down-ranks the candidate

### Requirement: Positive-signal prioritization
BEEP SHALL deterministically raise candidate ranking when exact transcript evidence supports humor, laughter, excitement, screaming, surprise, emotional reactions, arguments, memorable quotes, unexpected events, impressive gameplay, failures, clutch moments, community-worthy moments, or story setup and payoff. Ordinary dialogue without an allowed positive signal SHALL NOT become a candidate solely because the model assigns a high confidence score.

#### Scenario: Strong viral moment
- **WHEN** exact transcript evidence supports one or more allowed viral signals
- **THEN** BEEP reflects the strongest signal and additional distinct signals in the final score and ranks the moment above otherwise comparable generic dialogue

#### Scenario: Model assigns high confidence to random dialogue
- **WHEN** a model assigns high confidence but supplies no allowed positive signal with exact in-range evidence
- **THEN** BEEP rejects the candidate rather than presenting random dialogue as a strong clip

#### Scenario: Multiple positive signals
- **WHEN** a candidate contains more than one supported positive signal
- **THEN** BEEP lists the distinct signals and reflects their combined strength in its deterministic final score and rationale

### Requirement: Low-value-content down-ranking
BEEP SHALL lower candidate ranking when transcript evidence indicates music-only content, silence or dead air, repetitive conversation, low-energy dialogue, filler, or uncertain menu/loading context. Visual-only menu or loading conditions SHALL remain explicitly unverified unless transcript text supports the uncertainty.

#### Scenario: Meaningless or repetitive passage
- **WHEN** a candidate is dominated by a supported low-value signal and lacks a stronger positive signal
- **THEN** BEEP records the weakness and ranks it below candidates with meaningful viral evidence

#### Scenario: Positive and negative evidence coexist
- **WHEN** a candidate contains both strong positive evidence and a low-value passage
- **THEN** BEEP explains both and applies fixed positive-signal weights and low-value penalties rather than discarding either side

#### Scenario: Menu or loading state is not observable
- **WHEN** transcript-only analysis cannot establish whether the source shows a menu or loading screen
- **THEN** BEEP records that the condition cannot be verified and does not claim it detected visual content

### Requirement: Responsive analysis and failure recovery
BEEP SHALL run analysis outside the PySide6 UI thread, split long transcripts into bounded overlapping batches, use a configurable positive total request timeout for each local Ollama generation request, identify every batch by its ordinal position, and restore an actionable UI state after success, partial success, or failure without changing the completed transcript.

#### Scenario: Analysis is running
- **WHEN** local candidate analysis takes time to complete
- **THEN** the window remains responsive and displays the current batch number and progress

#### Scenario: Later batch times out
- **WHEN** one or more earlier batches produced validated candidates and a later batch exceeds the configured request timeout
- **THEN** BEEP identifies the failed batch, continues remaining batches, and returns the validated candidates as partial in-memory results

#### Scenario: No batch produces a valid result
- **WHEN** analysis cannot start or no valid structured candidate can be produced
- **THEN** BEEP shows the specific local setup or batch errors, preserves the transcript and existing candidates, and allows the user to retry

### Requirement: In-memory result lifecycle
Version 1 of BEEP SHALL persist a complete validated clip-candidate result when it belongs to a saved project. BEEP SHALL keep incomplete or unsaved candidate results in application memory only, SHALL NOT replace a project's last complete stored candidates with partial results, and SHALL discard memory-only results when the application closes.

#### Scenario: Complete valid candidates belong to a saved project
- **WHEN** every analysis batch completes successfully for a saved active project
- **THEN** BEEP atomically stores the ranked candidates in that project and keeps them available in the current application session

#### Scenario: Partial candidates belong to a saved project
- **WHEN** validated candidates survive from successful batches but one or more other batches fail
- **THEN** BEEP displays the partial candidates in memory, identifies the failed batches, and preserves the project's last complete stored candidate result

#### Scenario: Candidates do not belong to a saved project
- **WHEN** valid candidate results exist without a saved project to own them
- **THEN** BEEP displays them for the current session without writing them to SQLite

#### Scenario: Application restarts with memory-only candidates
- **WHEN** the user closes and reopens BEEP after generating unsaved or partial candidates
- **THEN** those memory-only candidate results are not restored

#### Scenario: Candidate persistence fails
- **WHEN** BEEP cannot atomically save a newly completed candidate result for a saved project
- **THEN** BEEP retains the project's last complete stored candidate result, reports the storage error, and keeps the newly generated candidates in memory for the current session
