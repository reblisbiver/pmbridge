# PMBridge Desktop Relay Zero-Touch Design

## Intent

Make the accepted PMBridge Desktop Relay path operational after macOS login without routine terminal setup, while keeping Desktop Relay, tunnel-client, and PMBridge dispatch/callback semantics unchanged.

## Goals

- Provide one PMBridge-owned operator surface for `status`, `doctor`, `start`, `stop`, `restart`, and `autostart enable|status|disable`.
- Retrieve the tunnel runtime key from macOS Keychain at process launch and never persist it in the repository, shell profile, plist, or logs.
- Manage the already-proven loopback Desktop Relay and tunnel-client processes idempotently, with bounded restart behavior and no duplicate instances.
- Preserve the existing PMBridge recovery LaunchAgent and callback queue semantics.
- Document the known-good versions, recovery, update, and bounded rollback path.
- Classify the prior `drain --json -> LOCKED, delivered=0, pending=1` observation using evidence; patch PMBridge core only if a reproducible callback correctness defect is demonstrated.

## Non-goals and anti-goals

- No IO Job Hunter changes.
- No Desktop Relay fork or upstream source changes.
- No public or LAN listener.
- No Commander Plus browser, GUI, mission, video, OCR, or knowledge features.
- No changes to PMBridge dispatch, deduplication, or callback semantics solely to make productionization tests pass.
- No live credentials in committed files, issue comments, screenshots, or command output.

## Chosen approach

Use a thin PMBridge-owned Python runtime module and CLI namespace, `pmbridge relay ...`, while retaining `pmbridge recovery` as the existing job-recovery entrypoint. A single launchd supervisor process owns the relay and tunnel-client children; it reads both credentials from Keychain into child environments, writes only redacted state/logs, restarts failed children with bounded backoff, and uses process-group ownership plus pid metadata to avoid duplicate instances. The relay remains configured on `127.0.0.1` and the tunnel profile uses `env:CONTROL_PLANE_API_KEY` and `env:DESKTOP_RELAY_AUTH`.

The wrapper accepts explicit paths/configuration through a non-secret JSON config under `~/.pmbridge/relay/`, generated from the known-good runtime paths. The launchd plist contains only absolute executable/config/log paths and no secrets. A dedicated stable Desktop Relay bearer credential is stored in Keychain alongside the control-plane API key; neither value is emitted by status or doctor.

Two independent LaunchAgents were rejected because their startup ordering and duplicate-process behavior would be harder to reason about and would duplicate lifecycle logic. Desktop Relay's upstream launch behavior remains untouched.

## Interfaces

```text
pmbridge relay status [--json]
pmbridge relay doctor [--json]
pmbridge relay start [--json]
pmbridge relay stop [--json]
pmbridge relay restart [--json]
pmbridge relay autostart enable|status|disable [--json]
```

The commands are idempotent. `status` and `doctor` return component-level states, PIDs, loopback addresses, pinned versions, Keychain presence booleans, and redacted errors; they never return credential values.

## Acceptance behavior

- Missing Keychain credentials produce `NOT_READY` with an actionable credential-name message and no secret material.
- `start` on a healthy runtime is a no-op success; `stop` only terminates children owned by the wrapper; `restart` is stop-then-start with one supervisor.
- Launchd uses the current user's `LaunchAgents` domain, `RunAtLoad`, `KeepAlive`, absolute paths, and a supervisor command that waits for relay readiness before starting tunnel-client.
- Killing either managed child is recovered without spawning a second child or dispatching a PMBridge job.
- The final acceptance uses one harmless relay call and one disposable PMBridge lifecycle, checking exactly one result and callback.

## Rollback

Disable and unload the PMBridge relay LaunchAgent, stop the managed supervisor, restore the pre-Phase-2 manual runtime configuration pinned to Desktop Relay commit `b8b64c8e4dc38e6a1e350b7d7a417023e1907535` and tunnel-client `0.0.19`, and leave PMBridge's existing recovery agent enabled. No PMBridge core rollback is required unless a separately evidenced correctness defect is found.
