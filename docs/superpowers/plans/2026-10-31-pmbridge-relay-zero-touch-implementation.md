# PMBridge Relay Zero-Touch Productionization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the accepted PMBridge Desktop Relay path start, recover, and diagnose itself after macOS login without routine terminal work.

**Architecture:** Add one PMBridge-owned `relay` runtime module and CLI namespace. A single launchd supervisor owns the loopback Desktop Relay and tunnel-client children, reads credentials from macOS Keychain, and exposes redacted status/doctor data. Keep PMBridge job recovery and callback semantics unchanged.

**Tech Stack:** Python 3.9+, macOS `security` and `launchctl`, stock Desktop Relay, OpenAI tunnel-client `0.0.19`.

**Spec:** `docs/superpowers/specs/2026-10-31-pmbridge-relay-zero-touch-design.md`

## Global Constraints

- Do not fork or modify Desktop Relay unless a reproducible upstream defect is captured first.
- Do not modify IO Job Hunter.
- Do not modify PMBridge dispatch/callback semantics merely to make productionization tests pass.
- Keep relay listeners loopback-only.
- Never commit or print live tunnel/runtime secrets.
- Reuse existing Desktop Relay recovery/launch mechanisms where practical.
- WIP=1.

## Review Focus

- Credential absence/revocation: status is useful and redacted; start fails closed.
- Existing running instance: repeated start/autostart does not create duplicate daemons.
- Startup ordering: tunnel-client starts only after relay loopback readiness.
- Crash recovery: child death restarts the right component without duplicate PMBridge work.
- Drain lock state: classify without changing callback semantics unless correctness fails.

---

### Task 1: Classify drain lock state

**Files:**
- Create: `docs/acceptance/issue5-drain-classification.md`
- Test only if a correctness defect is reproduced

- [ ] Capture current pending/delivered state and one accepted callback observation.
- [ ] Verify no duplicate dispatch, no duplicate callback, and no silent callback loss.
- [ ] Document the benign lock-contention/stale-observability classification if the callback remains correct.
- [ ] Do not change PMBridge core code unless a failing regression test proves a real defect.

### Task 2: Add Keychain-backed relay runtime model

**Files:**
- Create: `pmbridge/relay_runtime.py`
- Modify: `pmbridge/cli.py`
- Test: `tests/test_relay_runtime.py`

**Interfaces:**
- `pmbridge relay status|doctor|start|stop|restart`
- `KeychainStore.get(name) -> str | None`
- `RelayRuntime.status() -> dict`
- `RelayRuntime.doctor() -> dict`
- `RelayRuntime.start() -> dict`
- `RelayRuntime.stop() -> dict`
- `RelayRuntime.restart() -> dict`

- [ ] Write failing tests for missing credentials, redacted status, idempotent start, and stopped state.
- [ ] Verify the focused tests fail for the missing module/commands.
- [ ] Implement Keychain lookup through `security find-generic-password`; capture stdout in memory only and never include it in returned payloads or logs.
- [ ] Implement safe process ownership metadata and redacted component status.
- [ ] Implement idempotent start/stop/restart and relay-readiness ordering using the pinned external command paths.
- [ ] Run focused tests and the full existing suite.

### Task 3: Add launchd autostart and supervisor recovery

**Files:**
- Modify: `pmbridge/launchd.py`
- Modify: `pmbridge/cli.py`
- Modify: `pmbridge/relay_runtime.py`
- Test: `tests/test_relay_launchd.py`

**Interfaces:**
- `pmbridge relay autostart enable|status|disable`
- Generated plist uses absolute paths, `RunAtLoad`, `KeepAlive`, no secret values, and the current user's LaunchAgents domain.

- [ ] Write failing plist validation tests for absolute paths, no secret material, loopback-only relay, and restart policy.
- [ ] Implement a single supervisor entrypoint that owns both children and uses bounded retry/backoff.
- [ ] Implement launchd install/load/unload/status without duplicating lifecycle logic.
- [ ] Run focused tests and inspect generated plist.

### Task 4: Pin versions and publish operator runbook

**Files:**
- Create: `docs/PMBRIDGE_RELAY_RUNBOOK.md`
- Create: `docs/acceptance/issue5-drain-classification.md`
- Modify: `README.md`

- [ ] Document Desktop Relay commit `b8b64c8e4dc38e6a1e350b7d7a417023e1907535` and tunnel-client `0.0.19`.
- [ ] Document Keychain setup/rotation without shell-history exposure, operator commands, health checks, and bounded rollback.
- [ ] Document the drain lock classification and exact evidence boundary.
- [ ] Verify every documented command against a temporary home or the live runtime without printing secrets.

### Task 5: Final zero-touch acceptance

- [ ] Install a stable relay credential in Keychain without printing it.
- [ ] Enable the launch agent and verify status/doctor with no manual secret export.
- [ ] Restart/kill managed components and verify recovery without duplicate processes.
- [ ] Run one harmless ChatGPT relay call and one disposable PMBridge worker lifecycle.
- [ ] Verify exactly one result and callback, then return PMBridge to idle.
- [ ] Verify autostart disable and rollback path.
- [ ] Post the structured Issue #5 completion comment with A/B/C verdict and evidence matrix.
