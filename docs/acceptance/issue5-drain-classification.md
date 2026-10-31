# Issue #5 Drain Classification

Date: 2026-10-31

## Observation

During the Issue #5 acceptance sequence, after the single disposable worker completed, a direct `pmbridge drain --json` invocation reported lock contention:

```json
{"status":"LOCKED","delivered":0,"pending":2}
```

The lock was the existing non-blocking `event-drain.lock` path in `pmbridge/events.py`; a background drain held the lock, so the direct invocation returned without consuming events. The Issue #5 worker's completion callback was nevertheless delivered in the active bound ChatGPT conversation exactly once and its event is present under `events/delivered`:

```text
PM_JOB_STATUS 77b88c01-43a2-432c-9aa1-fa5f50dbb5d7 completed role=issue5-zero-touch-worker target=21161730f97b569df9390e21eea8cdebb6597b51
```

The worker result was `completed`, exit code `0`, with `writes=1`; no second worker was dispatched and the PMBridge HEAD and tracked files were unchanged. A later read-only check found one unrelated historical `oneeo-performance-management` event still pending because its bound conversation was not the active Edge tab; it is not an Issue #5 callback.

The follow-up `UI_BUSY` observation was a separate, reproducible PMBridge transport false positive: the old DOM probe selected an editable code block instead of the ChatGPT composer. The probe now targets the ChatGPT composer by `aria-label` and excludes its placeholder text, with regression coverage in `tests/test_transport.py`.

## Current evidence

The post-acceptance read-only state on 2026-10-31 still shows one pending historical event and 191 delivered event files. `pmbridge context pmbridge --json` reports three callback records for the current binding and no active job. This is an operationally observable queue item, not evidence of a lost or duplicated callback.

## Classification

**The `LOCKED` result is benign local lock contention, not evidence of callback loss or duplication.** The separate `UI_BUSY` result was a reproduced callback-delivery gating defect in the Edge composer probe and is fixed by the bounded selector/placeholder change. The accepted callback evidence proves the tested worker lifecycle was ultimately delivered exactly once.

## Decision

No dispatch, deduplication, or callback semantics were changed. The production wrapper reports runtime health separately from queue/lock diagnostics and never silently retries worker dispatch. The only PMBridge core change is the failing-test-backed Edge composer probe correction described above.
