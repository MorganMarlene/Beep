## ADDED Requirements

### Requirement: Exact transcript segment identity
BEEP SHALL treat transcript segments with identical start timestamp, end timestamp, and text as duplicate records and present that exact segment once. BEEP SHALL preserve identical text as separate transcript segments whenever its timestamps differ, because repeated words at distinct source times may be legitimate speech.

#### Scenario: Persisted exact segment is duplicated
- **WHEN** a stored project contains more than one transcript record with the same start timestamp, end timestamp, and text
- **THEN** BEEP restores and renders that exact segment once without changing its timestamp or text

#### Scenario: Speaker repeats the same words later
- **WHEN** two transcript segments contain identical text at different source timestamps
- **THEN** BEEP preserves and renders both timestamped segments in their original order

#### Scenario: New transcription produces an exact duplicate record
- **WHEN** faster-whisper returns the same start timestamp, end timestamp, and text more than once
- **THEN** BEEP saves and displays one copy while preserving every other distinct timestamped segment
