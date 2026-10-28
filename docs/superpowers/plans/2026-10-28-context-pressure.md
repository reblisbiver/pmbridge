# Context-Pressure Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add progressive evidence retrieval, PM-controlled durable ledger state, and objective context-pressure diagnostics without restricting PM access or judgment.

**Architecture:** Keep raw job evidence as the durable source layer. Add deterministic compact views above it and a project-scoped arbitrary ledger beside it; expose diagnostics as measurements only. Record job git boundaries at lifecycle events so compact inspection can accurately index changed state without replaying execution logs.

**Tech Stack:** Python 3 stdlib, existing PMBridge CLI/runtime, pytest/unittest.

**Spec:** `docs/context-pressure-design.md`

## Global Constraints
- Raw evidence remains available and unmodified.
- No automatic rotation, deletion, acceptance, authorization cadence, or log-read prohibition.
- Model/reasoning pinning remains unchanged.
- Existing callback delivery semantics remain unchanged.
- Existing project/runtime state remains backward-compatible.

## Review Focus
- Legacy jobs without git boundary fields still inspect cleanly.
- Huge raw logs are measured, not read into the compact packet.
- Arbitrary ledger JSON survives round trips without semantic rewriting.
- Context diagnostics scope metrics to the selected project/current binding where timestamps permit.
- Handoff remains usable when no ledger exists.

---

### Task 1: Evidence packet and git lifecycle metadata
**Files:** create `pmbridge/evidence.py`; modify `pmbridge/jobs.py`, `pmbridge/watcher.py`; test `tests/test_evidence.py`.
**Interfaces:** produces `evidence.inspect_job(home, job_id) -> dict`.
- [ ] Add failing tests for compact inspection, raw log non-ingestion, legacy jobs, and git boundary metadata.
- [ ] Run focused tests and observe failure.
- [ ] Implement git head capture and deterministic compact packet.
- [ ] Run focused tests green.
- [ ] Commit.

### Task 2: PM-controlled durable ledger
**Files:** create `pmbridge/ledger.py`; modify `pmbridge/cli.py`, `pmbridge/binding.py`; test `tests/test_ledger.py`.
**Interfaces:** `load`, `replace`, `patch`; handoff surfaces ledger metadata/content when present.
- [ ] Add failing round-trip/patch/handoff tests.
- [ ] Run focused tests red.
- [ ] Implement project-scoped arbitrary JSON ledger and CLI.
- [ ] Run focused tests green.
- [ ] Commit.

### Task 3: Context-pressure diagnostics
**Files:** create `pmbridge/context_pressure.py`; modify `pmbridge/cli.py`; test `tests/test_context_pressure.py`.
**Interfaces:** `context_pressure.report(home, project) -> dict`.
- [ ] Add failing project-scoping and byte/count tests.
- [ ] Run focused tests red.
- [ ] Implement metrics without thresholds or policy decisions.
- [ ] Run focused tests green.
- [ ] Commit.

### Task 4: Progressive-disclosure documentation/runtime
**Files:** modify `README.md`, `CHATGPT_SETUP.md`, `docs/spec.md` and runtime tests as needed.
- [ ] Update callback guidance to compact-first / raw-on-demand without weakening independent verification.
- [ ] Document `inspect`, `ledger`, and `context` commands and non-goals.
- [ ] Run full test suite and compileall.
- [ ] Commit.

### Task 5: Deploy and migrate existing bridges
**Files:** generic runtime plus compatibility helpers in each discovered legacy bridge where safe.
- [ ] Install merged generic runtime and verify commands.
- [ ] Add non-invasive compact evidence/ledger/context compatibility commands to IO Job Hunter and Bayesian Hardle legacy bridges without replacing their dispatch/callback systems.
- [ ] Verify legacy bridge existing tests plus new compatibility smoke tests.
- [ ] Update GitHub after final verification.
