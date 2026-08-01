# Security and Account-Linking Review

## Current security posture

### Current verified facts

- BEEP currently stores no credentials and has no Twitch/social account code. This is the correct state for the approved MVP.
- `ProjectRepository` stores source paths, metadata, transcript text, and candidate explanations in an unencrypted per-user SQLite file under `%LOCALAPPDATA%\BEEP` by default.
- Media remains outside SQLite; `.gitignore` excludes local data, credentials-like local configuration, media, models, transcripts, exports, and `.venv`.
- Ollama traffic uses fixed loopback URLs at `127.0.0.1:11434`. No remote AI SDK is present.
- SQL values are parameterized, candidate model output is structurally validated, and timestamps are derived from trusted transcript segment boundaries.
- No application-wide redacted logging policy, credential vault, privacy policy, support-bundle flow, code signing, installer, or updater exists.

### Current findings

| Severity | Classification | Finding | Recommendation |
|---|---|---|---|
| High | Verified | Transcripts and source paths are plaintext local data. Any process/user with access to the Windows account can read the database. | Document this clearly now; later offer protected backups or optional data protection based on an explicit threat model. Do not imply SQLite is encrypted. |
| Medium | Verified | Detailed FFmpeg, SQLite, filesystem, and Ollama errors can include local paths and machine details in the UI. | Separate short user guidance from copyable technical detail; redact tokens and query parameters before adding logs/support bundles. |
| Medium | Verified | Ollama loopback has no BEEP-specific authentication. Another local process can contact the service, and BEEP cannot prove service ownership. | Treat Ollama as a local user-trusted dependency; validate response size/schema and document the boundary. Do not expose or bind a BEEP service externally. |
| Medium | Future risk | Transcript/model content is untrusted. It currently only produces validated candidate data, but future tool use could turn prompt injection into editing or publishing actions. | Keep AI output advisory; require deterministic policy/user approval for side effects and never let transcript text select credentials or destinations. |

## Critical future gates

### Critical — credential storage and authorization isolation (Future risk)

Refresh/access tokens must never be stored in the current SQLite columns, JSON configuration, environment files, logs, crash dumps, command lines, or Git. A distributed desktop client also cannot safely conceal a provider client secret.

Before the first account link, define:

1. **Credential vault:** Windows Credential Manager or a well-reviewed DPAPI-backed local vault scoped to the current Windows user. SQLite stores only an opaque `credential_ref`, provider, non-secret external account ID/display name, scopes, expiry/status, and timestamps.
2. **Public-client OAuth:** authorization code with PKCE where supported; high-entropy `state`, nonce where applicable, exact redirect validation, short-lived callback listener, timeout/cancel, and system browser. Never ship a reusable secret as if it were confidential.
3. **One authorization per connected account:** each Twitch source account and publishing destination has its own connection ID and credential reference. Linking another account must never overwrite or share the first token.
4. **Least privilege:** request incremental provider-specific scopes and show them before consent. Read VOD scope is distinct from publish/manage scope.
5. **Lifecycle:** refresh rotation, revocation, reauthorization, expired scope, provider account rename, disconnect, and credential deletion are explicit and testable.
6. **Identity confirmation:** after authorization, call the provider identity endpoint and display the actual account before linking it to a profile.

### Critical — automatic update trust (Future risk)

An updater executes code at the highest trust level BEEP has. Before implementation require:

- Authenticode-signed application and installer artifacts from a protected certificate/key process;
- a signed update manifest containing version, channel, architecture, minimum OS/app version, immutable artifact URL, size, and SHA-256;
- TLS plus signature verification independent of transport;
- anti-downgrade and channel-switch rules;
- download to a non-executable staging location, atomic replace through a dedicated signed updater, and rollback after failed health check;
- no update while destructive media/database work is active;
- backup/compatibility checks before schema-changing updates;
- documented certificate rotation, revocation, and compromised-release response;
- tamper, partial download, offline, proxy, rollback, and revoked-key tests.

## Account and profile domain model

The UI term **profile** should represent a creator/workspace identity, not credentials. Connections should be independent resources.

```text
Creator/Profile
  ├─ ProfileSourceAccount ── ConnectedAccount (Twitch A, its own authorization)
  ├─ ProfileSourceAccount ── ConnectedAccount (Twitch B, its own authorization)
  └─ ProfileDestination ───── ConnectedAccount (YouTube/TikTok/etc.)
                                      └─ credential_ref -> Windows vault

ConnectedAccount may be linked to several profiles only through an explicit
ProfileDestination relationship and a confirmation screen.
```

### Required invariants

- Provider plus external account ID is unique per local connection identity; do not use display names as keys.
- Source and destination roles are explicit; a Twitch source connection is not silently a publishing authorization.
- Shared publishing destinations use a many-to-many link. Sharing a connection does not copy its credential.
- Each action records profile ID, connected account ID, project/content ID, actor/policy, scopes used, and provider request/idempotency ID—never the token.
- Disconnecting a shared destination warns which profiles/jobs are affected and prevents new jobs before deleting the vault item.
- Reauthorization updates only the chosen connection.
- The UI always displays the exact source account and destination before automated or manual publishing.

## Social provider adapter security boundary

**High — Future risk:** no adapter boundary exists yet. Before the first platform, use bundled and signed adapters rather than arbitrary Python plugins. The application layer supplies a short-lived token retrieved from the vault only for the chosen connection; adapters cannot query the database or choose another account.

Each adapter must provide typed operations for authorization metadata, account identity, capability/limit validation, upload/publish, status, revoke/disconnect, and retry classification. It must enforce fixed official HTTPS hosts, bounded request/response bodies, certificate validation, redacted diagnostics, and platform-specific scope checks. Publishing operations require idempotency protection even when the platform lacks a native idempotency key.

## Automatic Twitch and publishing safety

### High — Future risk: automation must be a durable policy-driven queue

Automatic VOD detection, downloading, processing, scheduling, and publishing cannot be chained as UI callbacks. Use durable jobs with explicit states, attempts, next retry, authorization connection, content fingerprint, and idempotency key. A crash/restart must not duplicate downloads or posts.

### Required controls

- Per-profile enable/disable, source account allowlist, destination allowlist, schedule/time zone, and review policy.
- Default to review-before-publish until a separate proposal authorizes unattended publishing.
- Rate-limit-aware exponential backoff with jitter and a capped retry budget; never retry validation/auth errors blindly.
- Content hash/source VOD ID plus destination prevents duplicate ingestion/publishing.
- Explicit handling for deleted/private VODs, revoked tokens, changed scopes, provider outages, partial uploads, and schedule changes.
- Durable audit trail with redaction and bounded retention.
- Emergency global pause that does not delete queued data.

## Data, privacy, and logging

| Severity | Classification | Requirement |
|---|---|---|
| High | Future risk | Define data inventory and retention before storing account IDs, publishing history, analytics, or feedback. |
| High | Future risk | Approval/rejection learning data must retain provenance, model/prompt version, candidate/input version, and user action; offer export/delete and never repurpose private content silently. |
| High | Future risk | Crash reporting/telemetry must be opt-in or clearly disclosed and must exclude transcript text, paths, tokens, thumbnails, and provider payloads by default. |
| Medium | Verified | Current UI exposes paths and raw dependency diagnostics; useful locally, but future support export needs structured redaction. |
| Medium | Future risk | Database backups can contain private transcripts/account metadata. Store them under the user's profile with clear retention; vault credentials must not be copied into backups. |

## Small security changes in dependency order

1. Threat model and local-data disclosure for the current MVP.
2. Redacted diagnostic/error model and bounded support log.
3. Windows credential-vault abstraction with fake-vault tests; no platform yet.
4. Account/profile schema containing metadata and opaque credential references only.
5. OAuth PKCE flow for one Twitch sandbox account.
6. Multiple Twitch accounts with strict connection isolation.
7. Bundled publishing-adapter contract and fake provider.
8. One real destination account with manual publish only.
9. Shared destination linkage and explicit confirmation.
10. Durable scheduler/idempotent queue; still review-before-publish.
11. Unattended publishing policy and emergency pause.
12. Signing/release pipeline, then signed updater and rollback.

## Account-linking release checklist

- [ ] Threat model is reviewed for local malware, token theft, prompt injection, account confusion, duplicate publishing, and update compromise.
- [ ] Tokens exist only in the Windows vault and are independently referenced per connected account.
- [ ] OAuth state/PKCE/callback, identity confirmation, least scopes, refresh, expiry, revoke, and disconnect tests pass.
- [ ] No token/client secret appears in SQLite, logs, support bundles, command lines, environment dumps, crash reports, or Git.
- [ ] Shared destinations require explicit profile links and show every affected profile on disconnect.
- [ ] Every publish action shows/records exact profile, destination, content, policy, and idempotency identity.
- [ ] Provider adapters are bundled/signed, host-restricted, bounded, cancellable, and rate-limit aware.
- [ ] AI output cannot directly authorize, choose credentials, or publish.
- [ ] Automation has review defaults, durable state, capped retries, duplicate protection, and a global pause.
- [ ] Signed-update controls pass before any automatic updater is enabled.

This is an engineering security review, not legal advice. Provider terms, privacy obligations, child/user content considerations, and open-source distribution obligations need specialist review before commercial release.
