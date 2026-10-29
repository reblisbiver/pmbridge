# PMBridge V0.1 / vNext Phase 1 Spec

## Goal
PMBridge is a private-reuse-first local capability layer that lets a high-autonomy ChatGPT PM supervise local Codex execution as durable jobs, with recovery, evidence, and callback into the active ChatGPT conversation. The PM may maintain context, apply project methods, catch mistakes, and correct conflicts with project facts or prior decisions.

## Architectural layers

PMBridge separates four conceptual layers without creating four independent state systems:

1. **PM / Supervision** — the canonical PM operating charter and continuity guidance for the supervising PM.
2. **Project** — project config and the optional PM-controlled arbitrary JSON ledger. The ledger may contain whatever project-specific goal, state, decision, focus, blocker, or methodology fields the PM needs.
3. **Execution** — durable Codex jobs, worker roles, prompts, targets, skills/method choices carried by instructions, model/access/network settings, evidence, and results.
4. **Transport & Runtime** — binding, callback queue, Edge delivery protection, watcher ownership, recovery, and busy/idle delivery state.

`takeover` is the canonical read-only view across these layers. It composes existing config, ledger, job, evidence, event, binding, and PM-state sources. `handoff` remains a backwards-compatible read alias and must not become a separate state system.

PMBridge provides capability/infrastructure. It does not prescribe PM policy, invent owner authorization, require a review cadence, force a job topology, limit evidence access, or automatically decide when to stop or hand off.

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
- Jobs are durable JSON records under `~/.pmbridge/jobs/` with prompt/output/result files and optional git start/end commit metadata.
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
Existing project-specific bridges remain independent legacy installations. Compatibility helpers may adapt their existing evidence and ledger sources into the four-layer read shape, but this project does not migrate their state or alter their execution modes.

## Concurrent PM orchestration

PMBridge supports multiple simultaneous Codex jobs. Concurrency policy is controlled by the PM at dispatch time, not hard-coded at project level. Each job carries `role`, `access`, optional `target`, `model`, and `reasoning_effort`. Recommended workflows may use one writer and multiple readers, but the framework does not enforce that topology.

All Codex invocations explicitly pin their execution model. V0.1 defaults are `gpt-5.6-luna` with `xhigh` reasoning; per-job overrides are supported.

Codex status callbacks enter a durable FIFO event queue. Events are delivered to ChatGPT only after the PM logical state and web UI are both idle. This prevents concurrent worker completions from interrupting the PM or the user's active interaction.

### Per-job capability policy

Filesystem access is an optional PM override: `access` may be omitted, `read`, or `write`. When omitted, PMBridge must not inject a Codex sandbox/profile choice. `network` may be omitted, `none`, `local`, or `internet`. When omitted, PMBridge must not inject a Codex network policy. `local` selects a loopback-only named profile; `internet` selects a named profile with explicit public-domain allowance. Both require explicit `read` or `write` because the selected permission profile also defines filesystem policy.

Every Codex invocation explicitly passes the model and reasoning effort. Defaults are `gpt-5.6-luna` and `xhigh`; no bridge job may silently inherit a changed global/UI model setting.


## Chat conversation takeover

A project binding is durable and replaceable. `rebind` changes only the single active ChatGPT callback destination and increments a binding version; active jobs, watcher PIDs and pending events are not restarted or rewritten. Previous bindings are kept in local runtime history. `takeover` returns separate PM/Supervision, Project, Execution, and Transport & Runtime sections without exposing prompt/result contents. `handoff` preserves the older flat keys and derives them from the same takeover view.


## Progressive read views and project metrics

PMBridge provides progressive disclosure rather than evidence restriction. `inspect <job-id>` returns deterministic compact metadata and an index of raw evidence; raw logs, full results, diffs, tests and artifacts remain available. The default compact view may preview large result text, but a full-result path/command remains available.

A project may have an optional PM-controlled JSON ledger under `projects/<name>/pm-ledger.json`. PMBridge stores and versions the value but imposes no semantic schema and does not decide what the PM should remember or discard.

`context <project>` reports objective project metrics such as jobs, callbacks, raw-log bytes and result bytes for the current binding window when known. PMBridge MUST NOT use these metrics to automatically stop work, delete evidence, force a conversation takeover, prescribe review depth, or make acceptance/authorization decisions.
