# PMBridge Project Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give replacement PM conversations a first-class way to list registered PMBridge projects before any filesystem search.

**Architecture:** Add a read-only registry reader to `pmbridge.config` and expose it as `pmbridge projects list --json`. Update replacement-conversation setup guidance to list first, then takeover, with disk search only as fallback.

**Tech Stack:** Python stdlib, argparse, unittest, Markdown docs.

**Spec:** `docs/superpowers/plans/2026-11-01-project-discovery-design.md`

## Global Constraints
- Do not change existing project config format.
- Do not mutate project state while listing.
- Preserve takeover/handoff/rebind semantics.

## Review Focus
- Malformed/non-project directories under `projects/` should not crash listing.
- Missing repo paths should be reported, not silently dropped.
- Multiple registered projects must list deterministically.
- Empty registry must return an empty project list cleanly.
- Existing CLI commands must remain compatible.

---

### Task 1: Registered-project list API and CLI

**Files:**
- Modify: `pmbridge/config.py`
- Modify: `pmbridge/cli.py`
- Test: `tests/test_project_discovery.py`

**Interfaces:**
- Produces: `config.list_projects(home: Path) -> list[dict]`
- Produces: CLI `pmbridge projects list --json`

- [ ] Write failing tests for deterministic listing, empty registry, malformed entries, missing repo, and CLI parser/output.
- [ ] Run focused tests and confirm RED.
- [ ] Implement minimal registry reader and CLI plumbing.
- [ ] Run focused tests and confirm GREEN.

### Task 2: Replacement-PM guidance

**Files:**
- Modify: `CHATGPT_SETUP.md`
- Test: `tests/test_project_discovery.py`

**Interfaces:**
- Consumes: `pmbridge projects list --json`

- [ ] Add a failing documentation contract test requiring list-before-takeover and disk-search fallback wording.
- [ ] Run focused test and confirm RED.
- [ ] Update setup guidance minimally.
- [ ] Run focused and full test suites.
- [ ] Commit the bounded change.
