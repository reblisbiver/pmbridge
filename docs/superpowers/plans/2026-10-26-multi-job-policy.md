# Multi-job orchestration and explicit Codex policy

Goal: allow one PM to supervise multiple concurrent Codex jobs without callback interruption, while making execution policy explicit per job.

Requirements:
- Multiple jobs may run concurrently; no project-level single-job lock.
- Each job records free-form role, optional target, access mode (`read` or `write`), model, and reasoning effort.
- Access is chosen by the PM per dispatch, not fixed by project configuration. The framework does not hard-code one-writer-many-readers.
- Every Codex invocation explicitly sets model and reasoning effort. Defaults are `gpt-5.6-luna` and `xhigh`.
- `read` maps to Codex `read-only`; `write` maps to workspace-write via `--approve-for-me`.
- Completion/stall/interrupted callbacks are queued durably. A single drain lock delivers FIFO only when PM logical state is idle and the target ChatGPT UI is not generating and has no composer draft.
- PM can explicitly set logical state with `pmbridge pm busy|idle|status`.
- Event metadata preserves job id, role, target, project, and status so simultaneous reports are attributable.
- Recovery also attempts to drain pending PM events.
- Existing legacy bridges are not migrated. Only explicit model/reasoning pinning is added there.
