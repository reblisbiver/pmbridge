# PMBridge

PMBridge is a small local supervisor that connects a ChatGPT Web conversation to local Codex execution.

**ChatGPT plans and reviews. Codex executes locally. PMBridge keeps the job durable and brings status back.**

This repository is optimized for personal reuse rather than broad compatibility. V0.1 intentionally supports one environment: macOS + Microsoft Edge + ChatGPT Web + Codex.

## What it does

- bootstraps a project without silently creating a Git repository;
- stores per-project config under `~/.pmbridge/projects/`;
- installs a stable runtime under `~/.pmbridge/runtime/` and command at `~/.pmbridge/bin/pmbridge`;
- launches Codex jobs with durable JSON state, logs, prompt and result files;
- detects completion, failure, stalls and interrupted jobs;
- periodically recovers lost watchers with a macOS LaunchAgent;
- sends short status callbacks to the exact ChatGPT Web conversation without foreground tab switching;
- provides `doctor` and real no-op `smoke` checks.

## Fastest setup: let ChatGPT do it

Open `CHATGPT_SETUP.md` from this repository in the ChatGPT conversation that should supervise the project, then ask ChatGPT:

> Read this setup protocol and connect my current project to PMBridge.

The protocol requires ChatGPT to ask before running `git init` when the target is not already a repository.

## Manual bootstrap

From this repository:

```bash
python3 -m pmbridge.cli bootstrap --repo /path/to/project --chat-url auto --json
```

If the result is `NEEDS_REPO_CONFIRMATION`, initialize only after deciding explicitly:

```bash
python3 -m pmbridge.cli bootstrap --repo /path/to/project --chat-url auto --init-repo --json
```

Then:

```bash
~/.pmbridge/bin/pmbridge doctor <project> --json
~/.pmbridge/bin/pmbridge smoke <project> --json
```

## Runtime commands

```text
pmbridge bootstrap   Configure a project and install/update the stable runtime
pmbridge doctor      Check project, Codex, Edge, ChatGPT tab and supervisor health
pmbridge run         Launch an approved Codex task as a durable job
pmbridge smoke       Launch a no-op end-to-end validation job
pmbridge recovery    Scan/recover active jobs
pmbridge notify      Return a short job status to the configured ChatGPT conversation
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
