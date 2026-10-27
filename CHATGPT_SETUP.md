# PMBridge setup protocol for ChatGPT

This file is the machine-facing setup contract. Prefer CLI JSON output over inferring behavior from implementation details.

## Purpose

Connect the user's current project to PMBridge so this ChatGPT web conversation can act as the supervisor/PM while Codex executes locally.

## Supported V0.1 environment

- macOS
- Microsoft Edge
- ChatGPT Web
- Codex CLI available from the ChatGPT desktop bundle or PATH
- Remote Desktop Commander available to this ChatGPT conversation for local setup/dispatch

## Setup procedure

1. Identify the target project directory from the user's request/current local context.
2. Choose one or two distinctive excerpts from the **user's recent messages in this exact ChatGPT conversation**. Do not use assistant-written text, conversation titles, generic project names, or broad keywords. PMBridge only searches user-message containers and refuses ambiguous/no-match bindings. Then run:

   ```bash
   python3 -m pmbridge.cli bootstrap --repo "<target-project-path>" --chat-bind-text "<recent distinctive user text>" --chat-bind-text "<another recent distinctive user text>" --json
   ```

3. Read the JSON status exactly.

### If status is `NEEDS_REPO_CONFIRMATION`

The target directory is not inside a Git repository. Do **not** initialize Git automatically.

Ask the user whether to create a new local Git repository for that project. Only after explicit approval rerun:

```bash
python3 -m pmbridge.cli bootstrap --repo "<target-project-path>" --chat-bind-text "<recent distinctive user text>" --chat-bind-text "<another recent distinctive user text>" --init-repo --json
```

### If chat binding fails

Automatic binding of the current Edge ChatGPT conversation failed. First retry with two distinctive recent user-message fragments from the current conversation. If binding still fails, ask the user to provide/confirm the exact current ChatGPT conversation URL, then rerun with:

```bash
python3 -m pmbridge.cli bootstrap --repo "<target-project-path>" --chat-url "<exact-chat-url>" --json
```

### If status is `READY`

Use the stable installed command reported in `runtime` (normally `~/.pmbridge/bin/pmbridge`). Then run:

```bash
~/.pmbridge/bin/pmbridge doctor <project-name> --json
```

Do not report PMBridge ready unless doctor returns `READY`.

4. Run one real end-to-end smoke job:

```bash
~/.pmbridge/bin/pmbridge smoke <project-name> --json
```

The command returns a job id. Wait for the callback in this same ChatGPT conversation:

```text
PM_JOB_STATUS <job_id> completed
```

Then inspect `~/.pmbridge/jobs/<job_id>.json` and the matching result file. The expected smoke result is `PMBRIDGE_SMOKE_OK`. Do not infer success from the callback alone.

5. For approved future Codex work, choose the execution policy **per job** and dispatch only through PMBridge. Access is never fixed at project level.

```bash
~/.pmbridge/bin/pmbridge run <project-name> \
  --role <free-form-role> \
  --access read|write \
  --network none|local \
  --target <optional-commit-or-version> \
  --model gpt-5.6-luna \
  --reasoning-effort xhigh \
  --file <task-file> \
  --json
```

`--access` is required so the PM makes the filesystem read/write decision explicitly for each job. `--network` is independently chosen per job (`none` by default, `local` for loopback-only access). Multiple jobs may run concurrently. One-writer/many-readers is a recommended QA topology, not a framework restriction. For browser/black-box testing against a host preview server, prefer `--access read --network local`: the repo remains read-only while localhost is reachable.

Unless there is a deliberate reason to override them, use the explicit defaults `gpt-5.6-luna` and `xhigh`. PMBridge always passes both values to Codex; never rely on the user's current Codex UI/config selection.

On callback, independently inspect local git state, diff, tests, job log/result, and artifacts. A completion callback is a **review trigger**, not by itself a decision about whether another task should be dispatched. Whether to continue, stop, or ask the user is determined by the PM from the user’s instructions and authorization in the current conversation. PMBridge does not impose a job-by-job, stage-by-stage, or other approval cadence.


## PM interaction / callback queue

Before beginning a substantial supervisor action that should not be interrupted by worker callbacks, mark the PM busy with a lease:

```bash
~/.pmbridge/bin/pmbridge pm busy --reason "<what the PM is doing>" --minutes 30 --json
```

When the PM is ready to receive worker reports again:

```bash
~/.pmbridge/bin/pmbridge pm idle --json
```

Worker callbacks are durable queued events. A single drain lock preserves FIFO order. Delivery is blocked while the PM is logically busy, ChatGPT is generating, the user has text in the composer, or the visible chat has not yet been quiet long enough. This prevents multiple workers from interrupting one another or the user's active exchange with the PM.

Each event preserves `job_id`, `role`, optional `target`, project and status. On callback, load the matching job JSON; do not guess which worker returned.

## GitHub remote rule

PMBridge bootstrap never creates or publishes a GitHub repository implicitly.

If there is no GitHub remote and the user wants one, first ask for explicit confirmation of:

- repository name
- public vs private visibility

Only then create the remote and perform the initial push through the appropriate GitHub tooling. Local `git init` approval does not imply permission to publish.

## Stability rule

Do not reconstruct PMBridge internals from memory. Always prefer the installed CLI's `--json` output and this protocol. If CLI output conflicts with older chat context, the current CLI output is the source of truth.


## Replacing a full ChatGPT PM conversation

When this ChatGPT conversation is approaching its context limit, start a new ChatGPT conversation rather than rebuilding PMBridge. In the new conversation:

1. Read this file.
2. Run `~/.pmbridge/bin/pmbridge handoff <project-name> --json` to load the durable execution state.
3. Rebind the project using two distinctive recent user-message fragments from the **new** conversation:

```bash
~/.pmbridge/bin/pmbridge rebind <project-name> \
  --chat-bind-text "<new-chat distinctive user text>" \
  --chat-bind-text "<another new-chat user text>" \
  --json
```

A successful rebind increments the binding version, records the previous binding in local history, and runs doctor against the new conversation. It does not restart Codex jobs or rewrite pending events. Pending events resolve the project's active chat URL only when drained, so they follow the project to the new conversation.

Treat only one binding as active. Do not keep two PM conversations competing for the same project.
