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
2. From the PMBridge source checkout, run:

   ```bash
   python3 -m pmbridge.cli bootstrap --repo "<target-project-path>" --chat-url auto --json
   ```

3. Read the JSON status exactly.

### If status is `NEEDS_REPO_CONFIRMATION`

The target directory is not inside a Git repository. Do **not** initialize Git automatically.

Ask the user whether to create a new local Git repository for that project. Only after explicit approval rerun:

```bash
python3 -m pmbridge.cli bootstrap --repo "<target-project-path>" --chat-url auto --init-repo --json
```

### If status is `NEEDS_CHAT_URL`

Automatic discovery of the current Edge ChatGPT conversation failed. Ask the user to provide/confirm the exact current ChatGPT conversation URL, then rerun with:

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

5. For approved future Codex work, dispatch only through:

```bash
~/.pmbridge/bin/pmbridge run <project-name> --file <task-file> --json
```

On callback, independently inspect local git state, diff, tests, job log/result, and artifacts. A completion callback is a **review trigger**, never permission to dispatch another task. Wait for explicit user approval before the next task.

## GitHub remote rule

PMBridge bootstrap never creates or publishes a GitHub repository implicitly.

If there is no GitHub remote and the user wants one, first ask for explicit confirmation of:

- repository name
- public vs private visibility

Only then create the remote and perform the initial push through the appropriate GitHub tooling. Local `git init` approval does not imply permission to publish.

## Stability rule

Do not reconstruct PMBridge internals from memory. Always prefer the installed CLI's `--json` output and this protocol. If CLI output conflicts with older chat context, the current CLI output is the source of truth.
