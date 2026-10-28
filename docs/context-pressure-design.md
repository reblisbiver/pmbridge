# PMBridge Context-Pressure Design

## Goal
Reduce unnecessary ChatGPT PM context consumption without restricting PM judgment or evidence access.

## Boundary
PMBridge may store, index, measure, and expose execution evidence. It must not decide what the PM is allowed to inspect, when the PM must hand off, what claims are accepted, or what project facts the PM must keep/drop.

## Design
1. **Compact evidence packet**: `pmbridge inspect <job-id>` returns job metadata, final result text, raw evidence paths/sizes, and exact git start/end boundaries with diffstat when available. Raw logs/results remain untouched and directly accessible.
2. **Durable PM ledger**: project-scoped arbitrary JSON controlled by the PM. PMBridge stores/version-stamps it but imposes no semantic schema.
3. **Context doctor**: `pmbridge context <project>` reports objective proxies (jobs/callbacks/evidence bytes/result bytes since the current binding, ledger metadata). It never auto-rotates, blocks work, or deletes evidence.
4. **Progressive disclosure docs**: callback guidance starts from the job record/compact packet and expands to raw log/diff/tests/artifacts whenever material. Independent verification remains mandatory; exhaustive raw-log ingestion is not.

## Non-goals
- No raw-log read ban or truncation policy.
- No automatic handoff threshold.
- No LLM-generated summary treated as source of truth.
- No deletion/compaction of the ChatGPT Web transcript.
- No fixed PM review or authorization cadence.
