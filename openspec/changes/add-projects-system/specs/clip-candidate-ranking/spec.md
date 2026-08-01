## MODIFIED Requirements

### Requirement: In-memory result lifecycle
Version 1 of BEEP SHALL persist a complete validated clip-candidate result when it belongs to a saved project. BEEP SHALL keep candidate results in application memory only when no saved project owns them, SHALL NOT write those unsaved results to SQLite, and SHALL discard unsaved results when the application closes.

#### Scenario: Valid candidates belong to a saved project
- **WHEN** analysis completes successfully for a saved active project
- **THEN** BEEP atomically stores the ranked candidates in that project and keeps them available in the current application session

#### Scenario: Saved project is reopened
- **WHEN** the user opens a saved project after restarting BEEP
- **THEN** BEEP restores that project's complete ranked candidate results without rerunning analysis

#### Scenario: Candidates do not belong to a saved project
- **WHEN** valid candidate results exist without a saved project to own them
- **THEN** BEEP displays them for the current session without writing them to SQLite

#### Scenario: Application restarts with unsaved candidates
- **WHEN** the user closes and reopens BEEP after generating candidates that did not belong to a saved project
- **THEN** those unsaved candidate results are not restored

#### Scenario: Candidate persistence fails
- **WHEN** BEEP cannot atomically save a newly completed candidate result for a saved project
- **THEN** BEEP retains the project's last complete stored candidate result, reports the storage error, and keeps the newly generated candidates in memory for the current session
