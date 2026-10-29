# PMBridge

PMBridge is a small local capability layer that connects a ChatGPT Web PM conversation to local Codex execution.

**The PM plans, directs, reviews, and reports. Codex executes locally. PMBridge keeps execution durable and brings evidence back.**

This repository is optimized for personal reuse rather than broad compatibility. V0.1 intentionally supports one environment: macOS + Microsoft Edge + ChatGPT Web + Codex.

## What it does

- bootstraps a project without silently creating a Git repository;
- stores per-project config under `~/.pmbridge/projects/`;
- installs a stable runtime under `~/.pmbridge/runtime/` and command at `~/.pmbridge/bin/pmbridge`;
- launches multiple concurrent Codex jobs with durable JSON state, logs, prompt and result files;
- detects completion, failure, stalls and interrupted jobs;
- periodically recovers lost watchers with a macOS LaunchAgent;
- queues concurrent worker callbacks and delivers them FIFO only when the PM/chat UI is idle;
- lets the PM choose filesystem access (`read`/`write`) and optional network policy (`none`/`local`/`internet`) per job, while allowing omission to inherit Codex network policy;
- explicitly pins every Codex job to `gpt-5.6-luna` + `xhigh` by default, with per-job overrides;
- provides `doctor` and real no-op `smoke` checks;
- exposes compact job evidence with raw evidence always available on demand;
- stores an optional PM-controlled durable ledger and reports diagnostic project metrics without forcing takeover or pruning.

## Architecture

PMBridge has four conceptual layers. They describe where information belongs; they do not impose a PM workflow or authorization policy.

- **PM / Supervision** — the durable PM operating charter and continuity guidance for a high-autonomy PM supervising execution agents.
- **Project** — project configuration plus the PM-controlled working state. The ledger is arbitrary JSON, so a project may record goals, current state, decisions, focus, blockers, and methodology in the shape that fits its work.
- **Execution** — Codex jobs, worker roles, targets, model/access/network choices, evidence, results, and job history.
- **Transport & Runtime** — the active ChatGPT binding, callback queue, Edge delivery guards, watcher ownership, recovery entrypoint, and PM busy/idle delivery protection.

`pmbridge takeover <project> --json` is the canonical read-only view over these layers. It composes existing state; it is not a new state store. `handoff` remains available as a backwards-compatible flat view for older PM conversations and scripts.

PMBridge supplies capability and infrastructure so the PM can exercise judgment. It does not prescribe review depth, approval cadence, job topology, context limits, automatic handoff, or what owner authorization means.

## Fastest setup: let ChatGPT do it

Open `CHATGPT_SETUP.md` from this repository in the ChatGPT conversation that should supervise the project, then ask ChatGPT:

> Read this setup protocol and connect my current project to PMBridge.

The protocol requires ChatGPT to ask before running `git init` when the target is not already a repository.
Automatic chat binding is ownership-sensitive: markers are matched only inside ChatGPT user-message containers, never against the whole page or assistant replies. Use recent distinctive user text; ambiguous or missing ownership fails closed.

## Manual bootstrap

From this repository:

```bash
python3 -m pmbridge.cli bootstrap --repo /path/to/project --chat-bind-text "<recent user text>" --chat-bind-text "<another recent user text>" --json
```

If the result is `NEEDS_REPO_CONFIRMATION`, initialize only after deciding explicitly:

```bash
python3 -m pmbridge.cli bootstrap --repo /path/to/project --chat-bind-text "<recent user text>" --chat-bind-text "<another recent user text>" --init-repo --json
```

Then:

```bash
~/.pmbridge/bin/pmbridge doctor <project> --json
~/.pmbridge/bin/pmbridge smoke <project> --json
```

Example concurrent dispatches controlled by the PM:

```bash
~/.pmbridge/bin/pmbridge run <project> --role implementer --access write --network internet --file implement.md --json
~/.pmbridge/bin/pmbridge run <project> --role qa --access read --network none --target <commit> --file audit.md --json
~/.pmbridge/bin/pmbridge run <project> --role blackbox --access read --network local --target <commit> --file explore.md --json
```

These are conventions, not fixed roles. The PM can create any role names. `--access read|write` is an optional override, not a required PMBridge policy: omit it when PMBridge should not impose a filesystem sandbox choice. Explicit `read` can block tasks that need to write local state or artifacts; PMBridge's watcher callback itself remains outside that Codex sandbox. `--network` is optional. Omit it to leave Codex network policy unchanged; use `none` to keep network disabled, `local` for loopback-only access, or `internet` for public outbound access. `local` and `internet` require explicit `--access` because named network profiles also define filesystem policy.

## Runtime commands

```text
pmbridge bootstrap   Configure a project and install/update the stable runtime
pmbridge doctor      Check project, Codex, Edge, ChatGPT tab and supervisor health
pmbridge takeover    Show the canonical four-layer read view for a PM takeover
pmbridge handoff     Backwards-compatible flat alias for the takeover view
pmbridge inspect     Show a compact evidence packet for one job; --full-result expands the result text
pmbridge ledger      Show/replace/patch PM-controlled durable project working state
pmbridge context     Report objective context-pressure metrics for a project
pmbridge rebind      Move a project callback binding to a new ChatGPT conversation
pmbridge run         Launch a Codex task; --access is optional; --network optionally supports none|local|internet
pmbridge smoke       Launch a no-op end-to-end validation job
pmbridge recovery    Scan/recover active jobs
pmbridge notify      Queue a short job status for the configured ChatGPT conversation
pmbridge drain       Drain queued PM events when PM/UI are idle
pmbridge pm          Set/read PM busy state
pmbridge watch       Internal watcher command
```

## State

PMBridge runtime data is deliberately outside project repositories:

```text
~/.pmbridge/
├── bin/pmbridge
├── runtime/pmbridge/
├── projects/<name>/config.json
├── projects/<name>/pm-ledger.json   # optional, PM-controlled
├── projects/<name>/bindings/history.jsonl
├── jobs/<job-id>.json
├── jobs/<job-id>.prompt.txt
├── jobs/<job-id>.log
├── jobs/<job-id>.result.txt
├── events/pending/ and events/delivered/
├── state/pm-state/                  # PM busy/idle delivery state
└── logs/
```

Do not commit runtime state, ChatGPT conversation URLs, job prompts/results or local paths into this public repository.


## Context-efficient supervision

A callback is a review trigger, not a requirement to ingest every byte of worker history. Start with `pmbridge inspect <job-id> --json` for deterministic job metadata, final-result preview, git boundaries/diffstat, and raw-evidence paths/sizes. Use `--full-result` or read the referenced raw log/result/artifacts whenever the task actually requires deeper evidence. PMBridge never forbids raw evidence access and never treats the compact packet as acceptance.

`pmbridge ledger show|replace|patch <project>` stores arbitrary JSON chosen by the PM. PMBridge does not impose a ledger schema or decide which project facts should be retained. `pmbridge context <project> --json` reports diagnostic project metrics such as counts and byte volumes since the current binding when that timestamp is known; it deliberately has no pressure threshold, automatic rotation, or policy recommendation.

## Existing legacy bridges

Existing project-specific bridges can remain independent. `compat/pm_context.py` provides a small layer-aware adapter for legacy evidence/ledger views; PMBridge does not migrate their state or execution modes.

## Codex permission profiles

Bootstrap installs namespaced local and internet Codex profiles under `$CODEX_HOME` (normally `~/.codex`). They are selected only when `--network local` or `--network internet` is explicit. Local profiles allow only loopback hosts; internet profiles explicitly allow public domains with `"*" = "allow"`. Omitting `--network` leaves Codex network policy untouched.


## Moving to a new ChatGPT conversation

When the PM conversation fills its context window, do not create a new bridge. In the new ChatGPT conversation, read `docs/pm-operating-charter.md` and `CHATGPT_SETUP.md`, then run `pmbridge takeover <project> --json` to inspect the four layers. Use `pmbridge handoff <project> --json` only for older consumers. Then run `pmbridge rebind <project> --chat-bind-text ... --json` to make the new conversation the single active callback destination. Running jobs and pending callbacks are preserved.
