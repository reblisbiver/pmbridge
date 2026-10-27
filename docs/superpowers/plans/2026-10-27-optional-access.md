# Optional Access Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop PMBridge from forcing a filesystem access mode on every Codex job while preserving explicit read/write controls when the PM wants them.

**Architecture:** Treat access as an optional per-job override. When omitted, record `null` and do not pass Codex sandbox/profile flags. When explicitly set, retain current read/write behavior. `network=local` still requires explicit access because the loopback profiles encode filesystem policy.

**Tech Stack:** Python stdlib, argparse, pytest.

**Spec:** User instruction in current conversation.

## Global Constraints
- PMBridge must not choose read or write on behalf of the PM.
- Explicit read/write behavior remains available.
- `network=local` must remain loopback-only and therefore requires an explicit filesystem policy.
- Existing callback/watcher behavior must remain unchanged.

## Review Focus
- Omitted access adds no `-s`, `-p`, or `--approve-for-me` flags.
- Explicit read remains read-only.
- Explicit write remains workspace-write/approve-for-me behavior.
- CLI accepts omitted `--access`.
- `network=local` without access fails clearly rather than silently choosing one.
