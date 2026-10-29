# PMBridge Binding Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a PM from a stale ChatGPT conversation from dispatching jobs after a project binding takeover, using only a local binding guard check.

**Architecture:** Store a binding session token and monotonically increasing binding version in the project config. Takeover and rebind return a compact guard containing the project, version, and session; guarded projects require that guard at `run`/`smoke`, while legacy configs without guarded mode remain compatible. Callback draining continues to resolve the current active binding. The installed runtime copy operation skips self-deletion when invoked from its own installed package.

**Tech Stack:** Python 3 stdlib, JSON config/state files, pytest/unittest, Markdown.

**Spec:** User task `PM_BRIDGE_TASK:3c69e757-e076-4b80-bcab-e5f3de2d6543` and `docs/spec.md`.

## Global Constraints

- Guard validation must compare only cheap local durable project config; no LLM, Codex, browser, DOM, or takeover/context read occurs on normal dispatch.
- A stale or missing guard in guarded mode refuses dispatch and explains that takeover/rebind is required.
- Rebind invalidates old guards and does not restart jobs, rewrite pending events, or change callback routing semantics.
- Existing configs without guarded mode remain dispatch-compatible until they opt into guarded mode through bootstrap/rebind.
- Do not invent authorization policy, approval cadence, job limits, review rules, or forced topology.
- Keep the runtime wrapper fix separate and limited to the proven self-install deletion case.

## Review Focus

- A malformed guard must fail closed without creating a job or starting a watcher.
- A guard for the right version but wrong session must be rejected, including same-URL rebinds.
- A guarded project with no guard must not silently downgrade to legacy behavior.
- Existing legacy projects and direct callers remain compatible until rebind/bootstrap enables guarded mode.
- A pending callback created before rebind still drains to the post-rebind active URL.

### Task 1: Binding guard and dispatch gate

**Files:**
- Modify: `pmbridge/binding.py`
- Modify: `pmbridge/cli.py`
- Test: `tests/test_binding.py`, `tests/test_runtime_cli.py`

**Interfaces:**
- `binding.guard(home, project) -> dict` returns `project`, `binding_version`, and `binding_session`.
- `binding.validate_guard(home, project, expected_guard) -> dict` returns `READY`, `LEGACY_UNGUARDED`, `BINDING_GUARD_REQUIRED`, `BINDING_GUARD_INVALID`, or `BINDING_GUARD_STALE` without reading browser/UI state.
- `cli.run_project(..., binding_guard=None)` validates before creating a job.
- `run` and `smoke` accept JSON `--binding-guard` input.

- [ ] Write the stale-binding dispatch test first.
- [ ] Run it and observe RED because the current dispatch surface has no guard gate.
- [ ] Implement the smallest local guard model, bootstrap/rebind activation, takeover/rebind return fields, and dispatch gate.
- [ ] Add matching, stale, rebind-invalidation, missing/legacy, malformed, and no-browser-read tests; run the focused suite GREEN.
- [ ] Commit the guard implementation.

### Task 2: Callback routing regression and setup migration

**Files:**
- Modify: `CHATGPT_SETUP.md`
- Modify: `README.md` if command reference needs alignment
- Test: `tests/test_event_queue.py`, `tests/test_runtime_cli.py`

- [ ] Write a pending-callback-after-rebind test and run it RED if current behavior differs.
- [ ] Keep callback drain behavior unchanged and make the regression test GREEN.
- [ ] Document that takeover/rebind output contains the guard and every guarded run must pass it; document legacy behavior exactly.
- [ ] Commit the routing regression and migration docs.

### Task 3: Runtime wrapper self-install protection

**Files:**
- Modify: `pmbridge/runtime.py`
- Test: `tests/test_runtime_cli.py`

- [ ] Write a test that runs `runtime.install()` with source package equal to its installed target and observes the current self-delete failure.
- [ ] Add only the path-equality guard around copy/remove, then run the test GREEN.
- [ ] Commit the independently testable runtime fix.

### Task 4: Final verification and clean handoff

- [ ] Run focused tests, full pytest, `python3 -m compileall -q pmbridge compat`, and `git diff --check`.
- [ ] Inspect the diff for scope, confirm `docs/bugfix-cross-project-drain.md` is untouched, and run a final status check.
- [ ] Commit any directly necessary correction and rerun all completion checks.

