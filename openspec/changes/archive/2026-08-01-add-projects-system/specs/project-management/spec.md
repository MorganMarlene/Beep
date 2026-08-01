## Purpose

Provide durable, local workspaces so users can organize multiple VODs and resume metadata, transcript, and clip-candidate review after restarting BEEP.

## ADDED Requirements

### Requirement: Create a project
BEEP SHALL allow the user to create a project with a non-empty project name and an optional brand name, and SHALL assign the project a stable identity independent of its display name. The brand name SHALL be descriptive metadata belonging only to that project and SHALL NOT create or reference a reusable profile.

#### Scenario: Valid project is created
- **WHEN** the user provides a non-empty project name and confirms New Project
- **THEN** BEEP creates and activates a new empty local project bearing that name and the supplied optional brand name

#### Scenario: Project name is empty
- **WHEN** the user attempts to create a project with a blank or whitespace-only name
- **THEN** BEEP does not create the project and clearly requests a project name

#### Scenario: Projects share a display name
- **WHEN** the user creates projects with the same project name
- **THEN** BEEP preserves them as separate projects with distinct stable identities

### Requirement: Multiple local projects
BEEP SHALL store multiple independent projects locally and SHALL associate each project's saved data only with that project.

#### Scenario: Two projects contain different VODs
- **WHEN** the user saves different VOD state in two projects
- **THEN** opening either project restores only the metadata, transcript, and candidates belonging to the selected project

### Requirement: Active project visibility
BEEP SHALL show the active project name and SHALL make project-dependent VOD processing actions unavailable when no project is active.

#### Scenario: Project becomes active
- **WHEN** the user creates or opens a project successfully
- **THEN** BEEP displays that project's name as the active project

#### Scenario: No project is active
- **WHEN** BEEP starts without an active project
- **THEN** the interface indicates that no project is active and does not save selected VOD state outside a project

### Requirement: Project-owned VOD state
BEEP SHALL save the active project's original VOD path, available probed video metadata, completed timestamped transcript segments, and validated AI clip candidates. BEEP SHALL preserve transcript text and timestamps exactly and SHALL preserve every displayed clip-candidate field.

#### Scenario: VOD metadata is loaded
- **WHEN** BEEP successfully probes a VOD while a project is active
- **THEN** BEEP saves the original media path and available filename, duration, resolution, frame rate, video codec, audio codec, bitrate, file size, and last-modified metadata for that project

#### Scenario: Transcription completes
- **WHEN** transcription completes successfully for the active project's VOD
- **THEN** BEEP atomically replaces that project's stored transcript with the completed ordered segments

#### Scenario: Clip analysis completes
- **WHEN** local AI clip analysis completes successfully for the active project
- **THEN** BEEP atomically replaces that project's stored candidates with the ranked validated candidates, including start and end timestamps, clip type, score, summary, selection reasoning, strong signals, and weaknesses or missing context

#### Scenario: Processing fails
- **WHEN** probing, transcription, analysis, or a persistence operation fails before a complete replacement is saved
- **THEN** BEEP retains the project's last complete stored data and reports the failure

### Requirement: Reopen and restore a project
BEEP SHALL allow the user to open an existing project and restore its saved VOD metadata, transcript, and AI clip candidates after application restart.

#### Scenario: Stored project is reopened
- **WHEN** the user opens an existing project after restarting BEEP
- **THEN** BEEP restores the project name, optional brand name, saved VOD details, ordered transcript, and ranked clip candidates into the current interface

#### Scenario: Project restoration fails
- **WHEN** BEEP cannot completely read a selected project
- **THEN** BEEP reports the real storage error and keeps the previously active project and its displayed data unchanged

#### Scenario: Original VOD is unavailable
- **WHEN** a project is reopened but its stored original VOD path no longer exists or is inaccessible
- **THEN** BEEP restores the saved metadata, transcript, and candidates, clearly marks the source VOD as unavailable, and disables actions that require the media file

### Requirement: Recent projects
BEEP SHALL provide a Projects section in the sidebar containing New Project and Open Project actions and a recent-project list containing at most 10 projects ordered by most recently opened or updated project.

#### Scenario: Recent projects are available
- **WHEN** BEEP starts and saved projects exist
- **THEN** the Projects section shows up to 10 of the most recently used projects in order and allows one to be opened

#### Scenario: No projects exist
- **WHEN** BEEP starts with an empty project database
- **THEN** the Projects section shows an empty-state message and keeps New Project available

#### Scenario: Open Project is selected
- **WHEN** the user invokes Open Project
- **THEN** BEEP presents the locally stored projects for selection without asking the user to locate a database or project file

### Requirement: Local SQLite storage
BEEP SHALL store project records and structured project data in a local SQLite database located outside the Git repository, SHALL store media paths rather than media bytes, and SHALL NOT require a network or cloud service.

#### Scenario: Project data is persisted
- **WHEN** BEEP saves a project
- **THEN** only structured project data and paths are written to SQLite and the original VOD remains at its existing filesystem location

#### Scenario: Network is unavailable
- **WHEN** the PC has no network connection
- **THEN** project creation, saving, listing, opening, and restoration continue to work locally

### Requirement: Version 1 project-data boundary
Version 1 SHALL NOT create or manage exported clips, titles, descriptions, thumbnails, publishing status, social accounts, reusable profiles, Twitch imports, editing state, posting state, project rename, project deletion, project duplication, project search, pinning, missing-media relinking, or automatic project reopening.

#### Scenario: Project is saved in Version 1
- **WHEN** BEEP persists the active project
- **THEN** it stores only project identity, optional project-specific brand name, VOD path and metadata, transcript segments, and AI clip candidates

#### Scenario: BEEP restarts
- **WHEN** the user launches BEEP after previously working in a project
- **THEN** BEEP shows recent projects without automatically reopening any project

#### Scenario: Original media is unavailable
- **WHEN** an opened project references a missing or moved VOD
- **THEN** BEEP reports the unavailable path without searching for, relinking, or modifying the stored media path
