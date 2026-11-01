# PMBridge Relay Zero-Touch Productionization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the accepted PMBridge Desktop Relay path start, recover, and diagnose itself after macOS login without routine terminal work.

**Architecture:** Keep stock Desktop Relay and the official OpenAI `tunnel-client` unchanged. Add only a thin PMBridge-owned operational wrapper around the already-proven local relay+tunnel runtime, using macOS Keychain for the runtime credential and launchd for lifecycle management. Treat PMBridge drain/callback behavior as a separate correctness observation: classify first, patch only if a reproducible correctness defect exists.

**Tech Stack:** macOS launchd, shell/Python control scripts already used by PMBridge, macOS Keychain (`security` CLI), stock Desktop Relay, OpenAI `tunnel-client v0.0.19`.

**Spec:** `docs/CURRENT_STATE_REMOTE_RELAY.md`

## Global Constraints

- Do not fork or modify Desktop Relay unless a reproducible upstream defect is captured first.
- Do not modify IO Job Hunter.
- Do not modify PMBridge dispatch/callback semantics merely to make productionization tests pass.
- Keep relay listeners loopback-only.
- Never commit or print live tunnel/runtime secrets.
- Reuse existing Desktop Relay recovery/launch mechanisms where practical.
- WIP=1.

## Review Focus

- Login/startup ordering: tunnel-client must not become healthy before its local relay target is ready.
- Credential absence/revocation: startup must fail closed and report a useful status without leaking the key.
- Process crash/restart: relay or tunnel-client death must recover without duplicate PMBridge dispatch/callback.
- Existing running instance: `start`/autostart must be idempotent and not create duplicate daemons.
- Drain lock state: `LOCKED, pending=1` must be classified and must not imply silent callback loss or duplicate delivery.

---

### Task 1: Classify the observed PMBridge drain lock state

**Files:**
- Read: existing PMBridge relay/drain scripts and state files
- Create only if needed: a focused regression test under the existing PMBridge test layout

**Interfaces:**
- Consumes: current `pmbridge drain --json` behavior and callback state
- Produces: a written classification: benign lock contention / stale observability / real callback correctness defect

- [ ] **Step 1:** Reproduce the accepted callback scenario with one disposable job and record drain/queue state before, during, and after callback delivery.
- [ ] **Step 2:** Verify no second dispatch occurs and no callback is silently lost.
- [ ] **Step 3:** If `LOCKED, pending=1` clears naturally or reflects an active delivery lock while callback correctness remains intact, document it as benign operational state; do not patch product code.
- [ ] **Step 4:** If it wedges, loses callbacks, or can duplicate delivery, add the smallest failing regression test first, then implement the bounded PMBridge fix and rerun focused tests.
- [ ] **Step 5:** Commit only if product/test code changed; otherwise leave evidence in the issue.

### Task 2: Add a secure local runtime wrapper

**Files:**
- Create/modify only inside the PMBridge repository following existing CLI/script conventions
- Do not edit Desktop Relay upstream checkout

**Interfaces:**
- Produces operator commands equivalent to: `status`, `doctor`, `start`, `stop`, `restart`
- Reads tunnel runtime key from macOS Keychain at process launch; does not persist plaintext key in repo or shell profile

- [ ] **Step 1:** Map the existing PMBridge script/CLI convention and select the minimal wrapper path/name without reorganizing the repo.
- [ ] **Step 2:** Add focused tests for missing key, already-running state, stopped state, and redacted status output.
- [ ] **Step 3:** Implement Keychain lookup/injection for `CONTROL_PLANE_API_KEY` and preserve the existing tunnel ID/profile without printing secrets.
- [ ] **Step 4:** Implement idempotent `start/stop/restart/status/doctor` orchestration for Desktop Relay + tunnel-client.
- [ ] **Step 5:** Run focused tests and existing PMBridge control-plane tests; commit.

### Task 3: Add launchd autostart and crash recovery

**Files:**
- Create launchd plist/template and install/uninstall/status logic under the PMBridge-owned wrapper area

**Interfaces:**
- Produces: `autostart enable`, `autostart status`, `autostart disable`
- Reuses Task 2 runtime wrapper; no duplicate lifecycle logic

- [ ] **Step 1:** Add tests/validation for generated launchd configuration: absolute paths, no plaintext secret, loopback target, restart policy.
- [ ] **Step 2:** Implement launchd install/uninstall/status using the current user LaunchAgents domain.
- [ ] **Step 3:** Ensure startup ordering/retry tolerates Desktop Relay not being ready immediately.
- [ ] **Step 4:** Verify killing tunnel-client causes bounded automatic recovery; verify killing relay/child does not create duplicate tunnel processes.
- [ ] **Step 5:** Commit after focused verification passes.

### Task 4: Pin, document, and verify rollback/update behavior

**Files:**
- Update: `docs/CURRENT_STATE_REMOTE_RELAY.md`
- Create: one concise operator runbook under `docs/`

**Interfaces:**
- Produces exact known-good versions/commit, update steps, rollback steps, health checks, and secret-rotation guidance

- [ ] **Step 1:** Record known-good Desktop Relay commit and `tunnel-client v0.0.19` in the wrapper/runbook without copying credentials.
- [ ] **Step 2:** Document `status`, `doctor`, `restart`, autostart controls, Keychain credential replacement, and rollback to the known-good relay ref.
- [ ] **Step 3:** Verify the documented commands on the live accepted setup.
- [ ] **Step 4:** Commit documentation.

### Task 5: Final zero-touch acceptance

**Files:**
- No product changes unless a real defect is discovered and separately evidenced

**Interfaces:**
- Consumes all prior tasks
- Produces final go/no-go evidence for retiring paid Remote Desktop Commander from routine PMBridge use

- [ ] **Step 1:** With autostart enabled, restart the managed relay/tunnel runtime (a full Mac reboot is optional if owner approval is required; otherwise use the closest launchd logout/login-equivalent lifecycle test available).
- [ ] **Step 2:** Verify `status`/`doctor` healthy with no manual secret export and no public/LAN listener.
- [ ] **Step 3:** Run one harmless ChatGPT tool call through `PMBridge Desktop Relay`.
- [ ] **Step 4:** Run one disposable full PMBridge worker lifecycle and verify exactly one callback/result.
- [ ] **Step 5:** Kill one managed component, verify automatic recovery, and repeat a harmless call without recreating the ChatGPT app.
- [ ] **Step 6:** Confirm rollback instructions and autostart disable path work.
- [ ] **Step 7:** Report PASS/FAIL matrix and recommend whether the paid Remote Desktop Commander can be removed from routine workflow.
