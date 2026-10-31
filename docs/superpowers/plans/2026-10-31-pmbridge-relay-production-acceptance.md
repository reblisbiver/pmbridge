# PMBridge Relay Production Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that the new `PMBridge Desktop Relay` transport can carry one complete PMBridge worker lifecycle end-to-end without using the paid Remote Desktop Commander transport or changing PMBridge/IO Job Hunter product logic.

**Architecture:** Use the already accepted transport path `ChatGPT -> OpenAI Secure MCP Tunnel -> Desktop Relay -> Desktop Commander -> Mac`. Exercise one disposable PMBridge job through the generic `reblisbiver/pmbridge` environment only, then inspect its callback/result through the same new transport.

**Tech Stack:** PMBridge CLI/runtime, Desktop Relay, Desktop Commander Local, OpenAI Secure MCP Tunnel, Codex worker.

**Spec:** `docs/CURRENT_STATE_REMOTE_RELAY.md`

## Global Constraints

- WIP=1.
- Do not modify IO Job Hunter.
- Do not modify generic PMBridge product logic merely to make this acceptance pass.
- Do not use the paid Remote Desktop Commander transport.
- Do not modify/fork Desktop Relay unless an observed transport defect is first captured as evidence.
- Do not expose a public/LAN relay listener.
- Do not include secrets in GitHub evidence.
- Use a disposable, non-product-destructive worker task.

## Review Focus

- Worker dispatch actually originates through the new relay, not a local/manual side path.
- Callback can be observed and inspected after worker completion through the same relay.
- Process/session interruption does not trigger duplicate worker dispatch.
- Acceptance does not mutate an unrelated project/worktree.
- Any failure is classified as PMBridge logic vs relay/tunnel transport vs Codex/runtime, rather than patched blindly.

---

### Task 1: Preflight the accepted transport and PMBridge runtime

**Files:**
- No product files should change.

**Interfaces:**
- Consumes: connected `PMBridge Desktop Relay` ChatGPT app and current generic PMBridge runtime.
- Produces: evidence that the relay, PMBridge context/status commands, and dispatch prerequisites are available before mutation.

- [ ] **Step 1: Verify relay command execution through the new connector**

Run a harmless exact command and record its stdout.

- [ ] **Step 2: Inspect generic PMBridge status/context**

Use the existing PMBridge status/context command(s) to identify the current bridge/runtime state and confirm no unrelated mainline job is active.

- [ ] **Step 3: Record preflight evidence**

Capture command names, bridge/context identifiers needed for the disposable test, and any blocker. Do not dump secrets or broad logs.

### Task 2: Dispatch one disposable Codex worker through PMBridge

**Files:**
- Create only a disposable acceptance artifact if the worker needs one; keep it outside unrelated project repos or under PMBridge-owned test/runtime storage.

**Interfaces:**
- Consumes: the preflight-confirmed PMBridge dispatch path.
- Produces: one unique disposable worker/job identifier and a deterministic completion result.

- [ ] **Step 1: Define the disposable assignment**

Use a non-destructive assignment whose success can be independently verified, e.g. create/write a unique acceptance marker in PMBridge-owned temporary/runtime storage and return the exact marker/path.

- [ ] **Step 2: Dispatch exactly one worker**

Use the existing PMBridge dispatch mechanism. Record the job/bridge identifier. Do not dispatch a second worker if the first call's outcome is uncertain; inspect first.

- [ ] **Step 3: Verify the worker became observable**

Inspect PMBridge state and confirm the unique worker/job appears once.

### Task 3: Observe callback and inspect final result

**Files:**
- No product files should change beyond the disposable artifact from Task 2.

**Interfaces:**
- Consumes: the unique worker/job identifier.
- Produces: structured evidence that worker completion/callback/result inspection all traverse the new relay path.

- [ ] **Step 1: Observe completion/callback**

Wait/inspect using existing PMBridge commands; do not poll aggressively and do not replay dispatch.

- [ ] **Step 2: Inspect structured final result**

Use the normal PMBridge result/context inspection path. Verify the expected marker/result and that the worker completed exactly once.

- [ ] **Step 3: Verify disposable artifact if one was created**

Read the acceptance marker through the new relay and confirm exact content/path.

### Task 4: Classify and report the production-acceptance outcome

**Files:**
- No product files should change.

**Interfaces:**
- Consumes: evidence from Tasks 1–3.
- Produces: one final verdict for the issue.

- [ ] **Step 1: Check for unintended mutations**

Verify IO Job Hunter and generic PMBridge product code were not changed by the acceptance run.

- [ ] **Step 2: Classify any failure before fixing**

If something failed, identify whether the failure belongs to transport/tunnel, Desktop Relay, PMBridge, Codex/runtime, or test setup. Do not implement a fix in this acceptance issue unless PM explicitly narrows scope after reviewing the evidence.

- [ ] **Step 3: Leave one structured completion comment**

Include:
- Verdict: `A — production path proven`, `B — viable with bounded blocker`, or `C — unsuitable for PMBridge production`.
- Exact lifecycle exercised.
- Unique job/bridge ID.
- PASS/FAIL for preflight, dispatch, worker observation, callback, final-result inspection, disposable artifact verification, no-unintended-mutation check.
- Any blocker and its layer classification.
- Whether any code/config changed.
- Recommendation for Phase 2 zero-touch productionization.
