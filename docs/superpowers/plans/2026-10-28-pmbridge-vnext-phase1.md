# PMBridge vNext Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PMBridge's architecture readable and usable as four layers while preserving current job, callback, recovery, evidence, and storage behavior.

**Architecture:** Add one canonical `takeover` read model that composes existing state sources into `supervision`, `project`, `execution`, and `runtime` sections. Keep `handoff` as a compatibility wrapper derived from that model, and keep legacy project bridges behind small adapters rather than migrating their state. Add a concise PM operating charter as the durable role/continuity anchor for replacement PM conversations.

**Tech Stack:** Python 3 stdlib, JSON files already used by PMBridge, `unittest`/pytest, Markdown docs.

**Spec:** `docs/spec.md` plus the owner-approved PMBridge vNext direction in the task request.

## Global Constraints

- PMBridge empowers a high-autonomy PM; it does not prescribe PM policy or act as an authorization-policy engine.
- Do not add per-turn contracts, arbitrary approval gates, fixed job limits, mandatory stop cadence, forced writer/reviewer topology, automatic handoff, or invented owner authorization.
- Keep raw evidence accessible and keep the PM-controlled project ledger schema-free.
- Preserve current job, callback, Edge delivery, watcher, recovery, binding, and busy/idle semantics.
- Do not migrate runtime storage to SQLite or perform a broad storage migration.
- Do not modify `docs/bugfix-cross-project-drain.md`.
- The canonical `takeover` view is read-only composition; no new source of truth is introduced.

## Review Focus

- Existing `handoff` consumers retain the current flat keys and values while gaining an explicit canonical layer view.
- A missing ledger, legacy job fields, or missing PM-state file still produces a usable takeover view.
- Compact views do not expose prompt contents or raw log contents, and raw evidence paths remain available.
- Arbitrary ledger JSON is surfaced unchanged rather than normalized into a mandatory project schema.
- Legacy bridges get an adapter-shaped view without changing their dispatch, watcher, or callback behavior.

## Approaches considered

1. **Replace `handoff` in place.** Rejected because changing its shape would break existing machine consumers and would keep the misleading transition-oriented name as the only contract.
2. **Add a canonical `takeover` view and derive `handoff` compatibility from it.** Recommended: one read-model builder, no new persistence, a clear name for replacement-PM setup, and a small compatibility surface.
3. **Introduce a new normalized project database or migrate all legacy bridges.** Rejected for phase 1 because it destabilizes runtime storage and violates the adapter/non-migration boundary.

---

### Task 1: Durable PM operating charter and setup entrypoint

**Files:**
- Create: `docs/pm-operating-charter.md`
- Modify: `CHATGPT_SETUP.md`
- Test: documentation assertions added in `tests/test_runtime_cli.py` only if needed to protect a machine-facing path

**Interfaces:**
- Produces the canonical human/machine-readable charter at `docs/pm-operating-charter.md`.
- Setup/takeover guidance reads the charter before bootstrap, dispatch, review, or replacement-PM takeover.

- [ ] **Step 1: Write the charter and update setup guidance.** Keep the charter short and operational: PM role, supervision loop, project-context responsibility, evidence/review responsibility, plain-language owner reporting, correction/reminder behavior, and the explicit non-policy boundary. Do not add permissions or prohibitions beyond the approved direction.
- [ ] **Step 2: Verify the guidance is discoverable.** Check the charter path, its first-read instruction in `CHATGPT_SETUP.md`, and that the setup protocol points replacement PMs to `takeover` while retaining `handoff` as a compatibility alias.
- [ ] **Step 3: Commit the documentation-only change.**

```bash
git add docs/pm-operating-charter.md CHATGPT_SETUP.md
git commit -m "docs: add canonical PM operating charter"
```

### Task 2: Canonical four-layer takeover read model

**Files:**
- Modify: `pmbridge/binding.py`
- Modify: `pmbridge/cli.py`
- Test: `tests/test_binding.py`, `tests/test_runtime_cli.py`

**Interfaces:**
- Produces `binding.takeover(home: Path, project: str, recent_limit: int = 8) -> dict`.
- Canonical output has top-level `status`, `project`, `supervision`, `execution`, and `runtime` keys:
  - `supervision`: PM role metadata and the canonical charter path/read-first marker.
  - `project`: project name, repo, and the unchanged PM-controlled ledger envelope under `working_state`.
  - `execution`: existing execution defaults plus active/recent job summaries.
  - `runtime`: active binding, pending callbacks, PM busy/idle delivery state, and non-mutating Edge/watcher/recovery capability metadata.
- Adds `pmbridge takeover <project> --json` as the canonical CLI surface.

- [ ] **Step 1: Write failing tests for layer separation and source reuse.** Assert all four layer keys, ledger pass-through, job summaries, pending events, PM-state visibility, charter metadata, and absence of prompt/result contents in the takeover packet. Assert that `takeover` does not write or mutate jobs/events/ledger.
- [ ] **Step 2: Run focused tests and verify RED.**

```bash
python3 -m pytest -q tests/test_binding.py tests/test_runtime_cli.py
```

Expected: failure because `binding.takeover` and the `takeover` parser/handler do not exist.

- [ ] **Step 3: Implement the canonical builder from existing sources.** Refactor the current handoff collection logic into `takeover`; read config, ledger, jobs, pending events, and PM state through their existing modules. Keep job filtering/order and evidence redaction behavior unchanged. Add only non-mutating descriptive runtime metadata.
- [ ] **Step 4: Run focused tests and verify GREEN.**

```bash
python3 -m pytest -q tests/test_binding.py tests/test_runtime_cli.py
```

- [ ] **Step 5: Commit the canonical read-model change.**

```bash
git add pmbridge/binding.py pmbridge/cli.py tests/test_binding.py tests/test_runtime_cli.py
git commit -m "feat: add four-layer takeover read model"
```

### Task 3: Backwards-compatible handoff and legacy adapter

**Files:**
- Modify: `pmbridge/binding.py`
- Modify: `compat/pm_context.py`
- Test: `tests/test_binding.py`, `tests/test_legacy_context.py`

**Interfaces:**
- `binding.handoff(...)` remains callable and keeps existing flat keys (`project`, `repo`, `active_binding`, `execution_defaults`, `active_jobs`, `recent_jobs`, `pending_events`, `ledger`). Its values are derived from `takeover`, not independently collected.
- The generic `handoff` result exposes the canonical model under `takeover` for consumers that need explicit layers.
- `compat/pm_context.py` adds a `takeover(root)` adapter and `takeover` CLI command using its existing legacy inspect/context/ledger sources; it does not emulate generic job/binding storage.

- [ ] **Step 1: Extend failing compatibility tests.** Assert old handoff keys still work, the nested canonical view is present, and the legacy adapter returns four explicit sections while preserving existing `inspect`, `context`, and `ledger` behavior.
- [ ] **Step 2: Run focused tests and verify RED.**

```bash
python3 -m pytest -q tests/test_binding.py tests/test_legacy_context.py
```

- [ ] **Step 3: Implement `handoff` as a derived compatibility view.** Preserve old field names and values, add a deprecation/read-model note in code/docs, and do not write new state.
- [ ] **Step 4: Implement the legacy adapter.** Reuse existing legacy functions; represent unavailable generic runtime capabilities explicitly instead of inventing binding, watcher, or recovery state.
- [ ] **Step 5: Run focused tests and verify GREEN.**

```bash
python3 -m pytest -q tests/test_binding.py tests/test_legacy_context.py
```

- [ ] **Step 6: Commit the compatibility change.**

```bash
git add pmbridge/binding.py compat/pm_context.py tests/test_binding.py tests/test_legacy_context.py
git commit -m "refactor: make handoff and legacy views layer-aware"
```

### Task 4: Align architecture/spec/README and replacement-PM instructions

**Files:**
- Modify: `README.md`
- Modify: `docs/spec.md`
- Modify: `docs/context-pressure-design.md`
- Modify: `CHATGPT_SETUP.md`

**Interfaces:**
- Documentation names the four conceptual layers consistently: PM/Supervision, Project, Execution, Transport & Runtime.
- Documentation identifies `takeover` as the canonical read view and `handoff` as the backwards-compatible alias.
- Documentation states that PMBridge supplies capability/infrastructure and preserves PM judgment, project-state flexibility, raw evidence access, and owner authorization boundaries.

- [ ] **Step 1: Update docs without changing runtime semantics.** Add the architecture map, state-source map, takeover/rebind flow, charter-first setup instruction, and compatibility/deprecation note. Reclassify `context` as diagnostic project metrics rather than a pressure policy. Clarify that legacy bridges are adapters/independent state systems.
- [ ] **Step 2: Review every changed doc against the approved anti-goals.** Remove wording that could imply mandatory approval cadence, fixed topology, automatic handoff, evidence restriction, or policy enforcement.
- [ ] **Step 3: Commit the documentation alignment.**

```bash
git add README.md docs/spec.md docs/context-pressure-design.md CHATGPT_SETUP.md
git commit -m "docs: align PMBridge with four-layer architecture"
```

### Task 5: Full verification and focused delivery

**Files:**
- Modify only files listed above unless a test exposes a directly necessary compatibility defect.

- [ ] **Step 1: Run focused tests for takeover, compatibility, and existing runtime contracts.**

```bash
python3 -m pytest -q tests/test_binding.py tests/test_legacy_context.py tests/test_runtime_cli.py tests/test_evidence.py tests/test_event_queue.py tests/test_recovery.py
```

- [ ] **Step 2: Run full pytest and compile checks.**

```bash
python3 -m pytest -q
python3 -m compileall -q pmbridge compat
```

- [ ] **Step 3: Inspect the final diff and status.** Confirm `docs/bugfix-cross-project-drain.md` was not touched, no runtime state or conversation URLs were added, and all commits are focused on phase 1.
- [ ] **Step 4: Commit any directly necessary test/doc correction, then rerun the complete verification commands.**

## Deferred beyond phase 1

- No SQLite/storage migration or broad legacy-state migration.
- No new authorization model, per-turn contract, approval gate, job limit, stop cadence, or forced writer/reviewer topology.
- No automatic context handoff, automatic evidence pruning, or threshold-based policy.
- No runtime rewrite of Edge delivery, watcher ownership, recovery scanning, or callback ordering.
- A deeper shared adapter framework for every project-specific bridge is deferred; phase 1 only keeps the existing compatibility adapter aligned and documents its boundary.
