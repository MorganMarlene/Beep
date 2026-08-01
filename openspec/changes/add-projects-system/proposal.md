## Why

BEEP currently treats the selected VOD and generated clip candidates as session state, so users cannot reliably organize multiple pieces of work or resume clip review after restarting the application. A small local project system provides a durable boundary for the existing metadata, transcript, and candidate workflow without introducing media management or cloud services.

## What Changes

- Add locally stored projects with a user-provided project name and optional brand name as project metadata only.
- Allow users to create a project, open an existing project, view recent projects, and see the active project name.
- Persist the original VOD path and its probed metadata, while leaving the media file outside SQLite.
- Persist timestamped transcript segments and validated AI clip candidates for saved projects, while retaining session-only in-memory candidates for unsaved projects.
- Restore saved metadata, transcript segments, and clip candidates when a project is reopened after BEEP restarts.
- Support multiple independent projects in one local SQLite database.
- Extend the existing sidebar with a Projects section, New Project and Open Project actions, the 10 most recent projects, and the active project name.
- Establish a project data model that can be extended by later approved changes, without storing exported clips, titles, descriptions, thumbnails, or publishing status in Version 1.
- Keep all storage and project operations local to the Windows PC.

## Capabilities

### New Capabilities

- `project-management`: Create, list, open, persist, and restore multiple local BEEP projects containing VOD metadata, transcripts, and AI clip candidates.

### Modified Capabilities

- `clip-candidate-ranking`: Replace the session-only candidate lifecycle with project persistence for saved projects while preserving in-memory-only behavior for unsaved projects.

## Impact

- Extends the local SQLite schema and data-access code with durable project identity, transcript ownership, and clip-candidate storage.
- Adds project lifecycle coordination so loading a project replaces the current in-memory view only after a complete successful read.
- Adds a small Projects section to the existing PySide6 sidebar and displays the active project name.
- Creates SQLite schema version 1 and a framework for future migrations, but no speculative legacy migration, new runtime dependency, remote service, media copying, or background worker system.
- Changes AI clip candidates from session-only state to project-owned persisted state when this change is implemented.
- Does not add reusable profiles, social posting, Twitch importing, video editing, exports, title or description generation, thumbnail generation, publishing workflows, project rename, project deletion, project duplication, project search, pinning, missing-media relinking, or automatic reopening.
