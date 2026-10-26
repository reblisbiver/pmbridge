# Legacy Bridge Hardening Note

Two existing project-specific bridge installations were intentionally left on their current execution modes rather than migrated into PMBridge.

Hardening was limited to non-invasive safeguards:

- pre-change and post-change local snapshots;
- a read-only bridge doctor for required files and runtime invariants;
- regression tests for the doctor;
- a protocol stability guard telling future agents not to migrate or change routing/execution semantics without explicit user instruction.

Their existing dispatch modes, project paths, conversation routing, watcher logic, and service configuration were not changed as part of PMBridge V0.1.

These legacy bridge files and their local configuration are not part of this public repository.
