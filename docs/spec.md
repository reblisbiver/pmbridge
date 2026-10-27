# PMBridge V0.1 Spec

## Goal
PMBridge is a private-reuse-first local bridge that lets a ChatGPT web conversation supervise local Codex execution as durable jobs, with recovery and callback into the originating ChatGPT conversation.

## Supported environment
- macOS
- Microsoft Edge
- ChatGPT Web
- Codex CLI/Desktop-installed CLI
- Remote Desktop Commander available to ChatGPT for setup/dispatch

## Bootstrap contract
- `pmbridge bootstrap --json --repo <path> --chat-url <url>` is the stable machine-facing entrypoint.
- If `<path>` is not inside a Git repository, bootstrap MUST return structured status `NEEDS_REPO_CONFIRMATION` and MUST NOT run `git init` unless `--init-repo` is explicitly provided.
- GitHub remote creation is out of implicit bootstrap scope. It must require a separate explicit command and user confirmation of repository name and visibility.
- If a repository exists, bootstrap creates/updates only PMBridge-owned local config under `~/.pmbridge/`; it does not modify project application files unless explicitly requested.

## Runtime
- A project config maps project name, repo root, ChatGPT conversation URL, Codex executable, and stall threshold.
- Jobs are durable JSON records under `~/.pmbridge/jobs/` with prompt/output/result files.
- A watcher launches Codex, owns the child process, tracks PID/status/activity/exit code, prevents terminal-state regression, and emits at-most-once state notifications.
- A recovery scanner reattaches only when a live Codex process has no live watcher, and marks genuinely orphaned active jobs interrupted.
- A launchd agent periodically runs recovery.

## Browser callback
- Edge transport targets an exact ChatGPT conversation URL.
- It must not activate/switch the user's foreground window.
- It must protect non-bridge composer text and use conservative submit/retry behavior.

## Doctor and smoke test
- `pmbridge doctor --json <project>` reports prerequisite/config/transport/supervisor health.
- `pmbridge smoke --json <project>` launches a no-op Codex job and reports its job id; the callback is the end-to-end success signal.

## ChatGPT setup protocol
- `CHATGPT_SETUP.md` instructs future ChatGPT models to use structured CLI output rather than reconstructing internals.
- If bootstrap returns `NEEDS_REPO_CONFIRMATION`, ChatGPT asks the user whether to initialize a local Git repository before rerunning with `--init-repo`.
- ChatGPT never creates a GitHub remote without a separate explicit user confirmation.

## Existing bridges
Existing project-specific bridges remain independent legacy installations. This project does not migrate or alter their execution modes.

## Concurrent PM orchestration

PMBridge supports multiple simultaneous Codex jobs. Concurrency policy is controlled by the PM at dispatch time, not hard-coded at project level. Each job carries `role`, `access`, optional `target`, `model`, and `reasoning_effort`. Recommended workflows may use one writer and multiple readers, but the framework does not enforce that topology.

All Codex invocations explicitly pin their execution model. V0.1 defaults are `gpt-5.6-luna` with `xhigh` reasoning; per-job overrides are supported.

Codex status callbacks enter a durable FIFO event queue. Events are delivered to ChatGPT only after the PM logical state and web UI are both idle. This prevents concurrent worker completions from interrupting the PM or the user's active interaction.

### Per-job capability policy

Filesystem access is an optional PM override: `access` may be omitted, `read`, or `write`. When omitted, PMBridge must not inject a Codex sandbox/profile choice. `network` may be omitted, `none`, `local`, or `internet`. When omitted, PMBridge must not inject a Codex network policy. `local` selects a loopback-only named profile; `internet` selects a named profile with explicit public-domain allowance. Both require explicit `read` or `write` because the selected permission profile also defines filesystem policy.

Every Codex invocation explicitly passes the model and reasoning effort. Defaults are `gpt-5.6-luna` and `xhigh`; no bridge job may silently inherit a changed global/UI model setting.


## Chat conversation handoff

A project binding is durable and replaceable. `rebind` changes only the single active ChatGPT callback destination and increments a binding version; active jobs, watcher PIDs and pending events are not restarted or rewritten. Previous bindings are kept in local runtime history. `handoff` returns a structured summary of project binding, active/recent jobs, pending events and execution defaults without exposing prompt/result contents.
