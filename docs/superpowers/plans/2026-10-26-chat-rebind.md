# Chat Rebind Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow a new ChatGPT web conversation to take over an existing PMBridge project without restarting jobs or losing pending callbacks.

**Architecture:** Keep project/job/event state durable and independent of a specific ChatGPT conversation. Add an explicit project binding layer that records a single active chat URL plus binding version/history. `rebind` changes only the active callback destination; `handoff` exposes a structured snapshot for the new PM conversation.

**Tech Stack:** Python stdlib, existing JSON config/state files, Edge conversation binding helpers.

**Spec:** `docs/spec.md`

## Global Constraints
- Never restart or mutate active Codex jobs during rebind.
- Exactly one active ChatGPT binding per project.
- Preserve prior bindings in local runtime history only; never commit conversation URLs.
- Pending callbacks must follow the current active binding at drain time.
- Rebind must use the same safe unique-chat discovery rules as bootstrap.

## Review Focus
- Rebinding while jobs are running must not change job PIDs/status.
- Pending callbacks created before rebind must deliver to the new active binding.
- Rebinding to the same URL should still be idempotent and auditable.
- Missing/ambiguous chat binding must not mutate config.
- Handoff output must not expose prompt/result contents by default.

---

### Task 1: Binding state and handoff snapshot

**Files:**
- Create: `pmbridge/binding.py`
- Test: `tests/test_binding.py`

- [ ] Write failing tests for config version increment, history append, job preservation, and handoff summary.
- [ ] Implement minimal binding/handoff state logic.
- [ ] Run tests and commit.

### Task 2: CLI and setup protocol

**Files:**
- Modify: `pmbridge/cli.py`
- Modify: `README.md`
- Modify: `CHATGPT_SETUP.md`
- Modify: `docs/spec.md`
- Test: `tests/test_runtime_cli.py`

- [ ] Write failing CLI parsing/behavior tests for `rebind` and `handoff`.
- [ ] Implement safe chat discovery and rebind command.
- [ ] Document new-conversation takeover flow.
- [ ] Run full suite and commit.

### Task 3: Merge and publish

- [ ] Run full tests, compile, privacy scan, and real local rebind dry-run using explicit URL restored afterward.
- [ ] Merge `feature/v0.1` into `main` locally and rerun tests on main.
- [ ] Create public GitHub repository `reblisbiver/pmbridge` and push `main`.
- [ ] Verify remote default branch and README.
