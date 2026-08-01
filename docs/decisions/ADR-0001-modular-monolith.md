# ADR-0001: Use a Small Modular Monolith

- Status: Accepted
- Date: 2026-08-01
- Applies to: BEEP Version 0.1

## Context

BEEP is a local Windows desktop application. Version 0.1 has one narrow workflow: select a video, inspect it, extract audio, transcribe it locally, display timestamped segments, and persist project data.

The application interacts with several distinct technologies—PySide6, ffprobe, FFmpeg, faster-whisper, and SQLite—but it does not need independent services, network APIs, distributed workers, or a generalized processing platform.

The broader product may eventually gain additional content-analysis and video-editing capabilities. Building infrastructure for those possibilities now would increase complexity before the core workflow has been validated.

## Decision

BEEP Version 0.1 will be implemented as a small modular monolith.

It will run as one desktop application and maintain clear responsibility boundaries for:

- PySide6 presentation
- Application workflow coordination
- Media inspection and audio extraction
- Local transcription
- SQLite persistence
- Minimal background execution

The implementation will prefer a small number of readable modules over deeply nested packages or speculative abstractions. External tools will be isolated at practical boundaries so important logic can be tested, but interfaces and layers will be added only when they solve an immediate Version 0.1 need.

Long-running FFmpeg and faster-whisper work will execute away from the PySide6 UI thread. This is a responsiveness requirement, not a reason to introduce a complex worker platform.

## Consequences

### Positive

- The application is straightforward to run and debug on one Windows PC.
- There are fewer failure modes than a service-based design.
- The end-to-end workflow can be delivered quickly.
- Clear module responsibilities still allow focused testing.
- External integrations can evolve without placing tool-specific code in the UI.
- Future architectural decisions can be based on observed needs.

### Tradeoffs

- Module boundaries rely on code discipline rather than deployment boundaries.
- Heavy tasks share the application's lifecycle.
- Some modules may need to be reorganized when later milestones are approved.
- SQLite and single-machine execution are not designed for multi-user or distributed processing, which is not a Version 0.1 requirement.

## Alternatives considered

### Full ports-and-adapters hierarchy

Rejected for Version 0.1 because the additional packages, interfaces, and mapping code would exceed the needs of the narrow workflow. Practical seams for subprocesses, transcription, and persistence are sufficient.

### Microservices or a local backend server

Rejected because BEEP runs on one computer and has no approved remote client or independently deployed service. This would add networking, lifecycle, packaging, and failure-handling complexity.

### General-purpose process and job system

Rejected because Version 0.1 needs only enough background execution to keep the UI responsive during one active workflow. A generalized queue would be premature.

### Put all logic in PySide6 widgets

Rejected because it would couple UI behavior to subprocesses, inference, and database operations, making testing difficult and risking UI freezes.

## Guardrail

This decision does not approve future feature scaffolding. New modules, abstractions, or dependencies must support an existing Version 0.1 requirement unless a later milestone is explicitly approved.
