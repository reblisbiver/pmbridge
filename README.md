# PMBridge

PMBridge is a small local supervisor that connects a ChatGPT Web conversation to local Codex execution.

**ChatGPT plans and reviews. Codex executes locally. PMBridge keeps the job durable and brings status back.**

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
- provides `doctor` and real no-op `smoke` checks.

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
pmbridge handoff     Show durable state for a replacement ChatGPT PM conversation
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
├── jobs/<job-id>.json
├── jobs/<job-id>.prompt.txt
├── jobs/<job-id>.log
├── jobs/<job-id>.result.txt
└── logs/
```

Do not commit runtime state, ChatGPT conversation URLs, job prompts/results or local paths into this public repository.

## Existing legacy bridges

Existing project-specific bridges can remain independent. PMBridge does not require migrating them.

## Codex permission profiles

Bootstrap installs namespaced local and internet Codex profiles under `$CODEX_HOME` (normally `~/.codex`). They are selected only when `--network local` or `--network internet` is explicit. Local profiles allow only loopback hosts; internet profiles explicitly allow public domains with `"*" = "allow"`. Omitting `--network` leaves Codex network policy untouched.


## Moving to a new ChatGPT conversation

When the PM conversation fills its context window, do not create a new bridge. In the new ChatGPT conversation, read `CHATGPT_SETUP.md`, then run `pmbridge handoff <project> --json` to inspect the durable state and `pmbridge rebind <project> --chat-bind-text ... --json` to make the new conversation the single active callback destination. Running jobs and pending callbacks are preserved.
