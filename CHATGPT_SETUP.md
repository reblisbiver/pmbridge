# PMBridge setup protocol for ChatGPT

This file is the machine-facing setup guide. Read `docs/pm-operating-charter.md` first, then prefer CLI JSON output over inferring behavior from implementation details.

## Purpose

Connect the user's current project to PMBridge so this ChatGPT web conversation can act as the supervisor/PM while Codex executes locally.

## Read first

Before bootstrap, dispatch, callback review, or replacement-conversation takeover, read the canonical PM operating charter at `docs/pm-operating-charter.md`. It defines the PM role and continuity expectations; it is not a per-turn contract or an authorization gate.

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
   bootstrap_json="$(python3 -m pmbridge.cli bootstrap --repo "<target-project-path>" --chat-bind-text "<recent distinctive user text>" --chat-bind-text "<another recent distinctive user text>" --json)"
   printf '%s\n' "$bootstrap_json"
   ```

3. Read the JSON status exactly.

### If status is `NEEDS_REPO_CONFIRMATION`

The target directory is not inside a Git repository. Do **not** initialize Git automatically.

Ask the user whether to create a new local Git repository for that project. Only after explicit approval rerun:

```bash
bootstrap_json="$(python3 -m pmbridge.cli bootstrap --repo "<target-project-path>" --chat-bind-text "<recent distinctive user text>" --chat-bind-text "<another recent distinctive user text>" --init-repo --json)"
printf '%s\n' "$bootstrap_json"
```

### If chat binding fails

Automatic binding of the current Edge ChatGPT conversation failed. First retry with two distinctive recent user-message fragments from the current conversation. If binding still fails, ask the user to provide/confirm the exact current ChatGPT conversation URL, then rerun with:

```bash
bootstrap_json="$(python3 -m pmbridge.cli bootstrap --repo "<target-project-path>" --chat-url "<exact-chat-url>" --json)"
printf '%s\n' "$bootstrap_json"
```

### If status is `READY`

Use the stable installed command reported in `runtime` (normally `~/.pmbridge/bin/pmbridge`). Keep the exact `binding_guard` object from the successful bootstrap JSON and serialize it for subsequent guarded commands:

```bash
binding_guard="$(printf '%s' "$bootstrap_json" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["binding_guard"], separators=(",", ":")))')"
```

Then run:

```bash
~/.pmbridge/bin/pmbridge doctor <project-name> --json
```

Do not report PMBridge ready unless doctor returns `READY`.

4. Run one real end-to-end smoke job:

```bash
~/.pmbridge/bin/pmbridge smoke <project-name> --binding-guard "$binding_guard" --json
```

The command returns a job id. Wait for the callback in this same ChatGPT conversation:

```text
PM_JOB_STATUS <job_id> completed
```

Then inspect `~/.pmbridge/jobs/<job_id>.json` and the matching result file. The expected smoke result is `PMBRIDGE_SMOKE_OK`. Do not infer success from the callback alone.

5. For Codex work that is within the user's current authorization, dispatch through PMBridge. Filesystem access can be left unspecified or explicitly overridden per job; PMBridge does not choose read or write on the PM's behalf.

```bash
~/.pmbridge/bin/pmbridge run <project-name> \
  --binding-guard "$binding_guard" \
  --role <free-form-role> \
  [--access read|write] \
  [--network none|local|internet] \
  --target <optional-commit-or-version> \
  --model gpt-5.6-luna \
  --reasoning-effort high \
  --file <task-file> \
  --json
```

`--access` is optional. If omitted, PMBridge does not add a Codex sandbox/profile override; the Codex invocation uses its own configured access behavior. Use `--access read` when the worker should be unable to modify the workspace, and `--access write` when it needs workspace writes. Be careful with `read`: although PMBridge's terminal callback is emitted by the watcher outside the Codex sandbox, a task that itself must write local state, artifacts, or bridge/sidecar files can be blocked by read-only access. `--network` is optional. If omitted, PMBridge does not override Codex network policy. Use `none` to keep network disabled, `local` for loopback-only access, or `internet` for public outbound access. `local` and `internet` use named profiles that also encode filesystem policy, so either requires an explicit `--access read|write`. Multiple jobs may run concurrently. One-writer/many-readers is only a possible topology, not a framework rule.

Unless there is a deliberate reason to override them, use the explicit defaults `gpt-5.6-luna` and `high`. PMBridge always passes both values to Codex; never rely on the user's current Codex UI/config selection.

On callback, independently verify the material claims and target state. Start with `~/.pmbridge/bin/pmbridge inspect <job-id> --json`, which is a compact evidence index: job metadata, final-result preview, git boundaries/diffstat when available, and paths/sizes for raw evidence. Expand into the raw log, full result, diff, tests, artifacts, or other local state whenever they are material, uncertain, contradictory, or otherwise useful. Do not treat the compact packet or a completion callback as acceptance. PMBridge never forbids raw evidence access. Whether to continue, stop, ask the user, or how deeply to audit is determined by the PM from the task and current user authorization; PMBridge imposes no review depth, job-by-job/stage-by-stage approval cadence, context threshold, or automatic takeover.


## PM interaction / callback queue

Before beginning a substantial supervisor action that should not be interrupted by worker callbacks, mark the PM busy with a lease:

```bash
~/.pmbridge/bin/pmbridge pm busy <project-name> --reason "<what the PM is doing>" --minutes 30 --json
```

When the PM is ready to receive worker reports again:

```bash
~/.pmbridge/bin/pmbridge pm idle <project-name> --json
```

Worker callbacks are durable queued events. A single drain lock preserves FIFO order. Delivery is blocked while the PM is logically busy, ChatGPT is generating, the user has text in the composer, or the visible chat has not yet been quiet long enough. This prevents multiple workers from interrupting one another or the user's active exchange with the PM.

Each event preserves `job_id`, `role`, optional `target`, project and status. On callback, use the matching job id; do not guess which worker returned.

For long-running projects, the PM may externalize its own current working state without changing execution semantics:

```bash
~/.pmbridge/bin/pmbridge ledger replace <project-name> --data '{"current_goal":"...","next":"..."}' --json
~/.pmbridge/bin/pmbridge ledger patch <project-name> --data '{"next":"..."}' --json
~/.pmbridge/bin/pmbridge ledger show <project-name> --json
~/.pmbridge/bin/pmbridge context <project-name> --json
```

Ledger content is entirely PM-controlled; PMBridge does not define required keys or delete chat history. `context` is diagnostic project metrics only and does not force compaction, rotation, or takeover.

## Takeover view

`~/.pmbridge/bin/pmbridge takeover <project-name> --json` is the canonical replacement-PM read view. It separates PM/Supervision, Project, Execution, and Transport & Runtime information while composing the existing durable sources. It does not mutate jobs, callbacks, ledger state, or bindings. Its `runtime.binding_guard` is the small local dispatch guard for the active binding. `handoff` remains a backwards-compatible flat alias for older setup scripts.

For a guarded project, pass that JSON guard to every `run` or `smoke` command:

```bash
~/.pmbridge/bin/pmbridge run <project-name> \
  --binding-guard '{"project":"<project-name>","binding_version":<version>,"binding_session":"<session>"}' \
  --instruction "..." --json
```

Guard validation reads only the project config and compares the project, binding version, and binding session locally; it does not run ChatGPT/Codex/browser/DOM discovery or read the takeover view on each dispatch. A matching guard starts the job. `BINDING_GUARD_REQUIRED`, `BINDING_GUARD_INVALID`, or `BINDING_GUARD_STALE` refuses the dispatch and requires takeover/rebind; PMBridge does not guess or auto-rebind. Projects created by bootstrap and projects after rebind are guarded. Existing configs without guarded mode remain legacy-compatible until bootstrap/rebind enables the guard.

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

1. Read `docs/pm-operating-charter.md`, then this file.
2. Run `~/.pmbridge/bin/pmbridge takeover <project-name> --json` to load the four-layer durable read view. The older `handoff` command remains a backwards-compatible alias.
3. Rebind the project using two distinctive recent user-message fragments from the **new** conversation:

```bash
~/.pmbridge/bin/pmbridge rebind <project-name> \
  --chat-bind-text "<new-chat distinctive user text>" \
  --chat-bind-text "<another new-chat user text>" \
  --json
```

A successful rebind increments the binding version, rotates the binding session, returns a fresh `binding_guard`, records the previous binding in local history, and runs doctor against the new conversation. Use that returned guard for subsequent `run`/`smoke` commands. Any guard from before the rebind is invalid, including when the URL is unchanged. Rebind does not restart Codex jobs or rewrite pending events. Pending events resolve the project's active chat URL only when drained, so they follow the project to the new conversation.

Treat only one binding as active. Do not keep two PM conversations competing for the same project.
