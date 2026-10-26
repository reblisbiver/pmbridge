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
- lets the PM choose filesystem access (`read`/`write`) and network access (`none`/`local`) independently for every job;
- explicitly pins every Codex job to `gpt-5.6-luna` + `xhigh` by default, with per-job overrides;
- provides `doctor` and real no-op `smoke` checks.

## Fastest setup: let ChatGPT do it

Open `CHATGPT_SETUP.md` from this repository in the ChatGPT conversation that should supervise the project, then ask ChatGPT:

> Read this setup protocol and connect my current project to PMBridge.

The protocol requires ChatGPT to ask before running `git init` when the target is not already a repository.

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
~/.pmbridge/bin/pmbridge run <project> --role implementer --access write --network none --file implement.md --json
~/.pmbridge/bin/pmbridge run <project> --role qa --access read --network none --target <commit> --file audit.md --json
~/.pmbridge/bin/pmbridge run <project> --role blackbox --access read --network local --target <commit> --file explore.md --json
```

These are conventions, not fixed roles. The PM can create any role names and choose access per job. `--network local` allows only loopback targets (`localhost`, `127.0.0.1`, `::1`) while preserving the selected filesystem access. This is intended for local preview servers and browser/black-box testing.

## Runtime commands

```text
pmbridge bootstrap   Configure a project and install/update the stable runtime
pmbridge doctor      Check project, Codex, Edge, ChatGPT tab and supervisor health
pmbridge run         Launch an approved Codex task; requires --access read|write and supports --network none|local
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

Bootstrap installs namespaced Codex profiles `pmbridge-read-local` and `pmbridge-write-local` under `$CODEX_HOME` (normally `~/.codex`). They are selected explicitly only for jobs using `--network local`. The read-local profile keeps the filesystem read-only while permitting full HTTP methods only to loopback hosts; it does not grant general internet access.
