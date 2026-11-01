# PMBridge Desktop Relay — Current Production Baseline

Last updated: 2026-10-31

## Final goal

Replace the paid Remote Desktop Commander transport for PM/agent work with a stable self-hosted path that lets ChatGPT reach this Mac and PMBridge without monthly tool-call quota pressure.

## Confirmed decisions

- Keep upstream Desktop Commander Local as the execution engine.
- Keep upstream `HashemKhalifa/desktop-relay` stock unless a real defect requires a bounded patch.
- Use the official OpenAI Secure MCP Tunnel as the primary remote transport.
- Do not continue the Cloudflare/domain path unless a future requirement specifically needs a public hostname.
- Do not fork Desktop Relay preemptively.
- Do not add unrelated Commander Plus capabilities (browser automation, mission orchestration, GUI control, SQLite DAGs, video/OCR, knowledge graph, etc.).
- WIP=1 for productionization tasks.

## Accepted evidence

### Issue #2 — local relay viability: ACCEPT

- Tested upstream Desktop Relay commit `b8b64c8e4dc38e6a1e350b7d7a417023e1907535`.
- Stock source required no changes.
- `pnpm test`: 11/11 passed.
- Local verification: 17/17 passed.
- Large-result paging, long-running operations, credential rotation/revoke, principal isolation, and Desktop Commander child recovery were exercised.

### Issue #3 — real ChatGPT path: ACCEPT

Real path exercised:

`ChatGPT custom MCP -> OpenAI Secure MCP Tunnel -> tunnel-client -> Desktop Relay -> Desktop Commander -> Mac`

All eight transport acceptance cases passed, including long-running commands, large-result paging, process lifecycle, Desktop Commander child recovery, and unauthorized-request rejection. A later manual recheck returned exact stdout for `printf 'manual-test-ok\n'`.

No Cloudflare hostname, public DNS, LAN listener, or paid Remote Desktop Commander transport was required.

### Issue #4 — PMBridge production path: ACCEPT

Real business path exercised:

`ChatGPT -> OpenAI Secure MCP Tunnel -> Desktop Relay -> Desktop Commander -> PMBridge -> Codex worker -> callback -> ChatGPT`

Accepted evidence:

- Exactly one disposable worker dispatched: `d333a057-53a5-46b1-b516-36421bd0d083`.
- Worker completed with exit code `0`.
- Structured result and disposable marker were verified through the new relay.
- Completion callback was visibly received in the bound ChatGPT conversation.
- PMBridge HEAD remained unchanged; tracked source was not modified.
- IO Job Hunter was not modified.
- Paid Remote Desktop Commander was not used.
- PMBridge returned to idle after the run.

Operational note: a manual `pmbridge drain --json` observation returned `LOCKED, delivered=0, pending=1` after the callback had already arrived through the active bound session. This did not invalidate acceptance and caused no duplicate dispatch. Treat it as a Phase 2 operability/observability check: only escalate to a product bug if it is reproducible as callback loss, queue wedging, or duplicate delivery.

## Current implemented state

- Core transport feasibility: complete.
- Real ChatGPT connector acceptance: complete.
- Real PMBridge worker lifecycle acceptance: complete.
- Desktop Relay remains loopback-only.
- Secure MCP Tunnel is functional.
- `openai/tunnel-client v0.0.19` is functional.
- ChatGPT app `PMBridge Desktop Relay` is connected and callable.
- No upstream Desktop Relay source fork is required.
- Production readiness is approximately 95%+: remaining work is zero-touch startup/recovery and operational hardening, not core capability development.

## Remaining work — Phase 2 only

### Phase 2 — zero-touch productionization

Goal: make normal use operationally boring and require no routine terminal work after macOS login.

Required operator outcomes:

- `status / doctor`
- `start / stop / restart`
- `autostart enable / status / disable`
- secure runtime-key storage, preferably macOS Keychain if practical
- launchd startup for Desktop Relay + tunnel-client
- crash/reconnect recovery
- pinned known-good upstream/runtime versions
- simple rollback/update procedure
- one-page recovery/runbook
- classify the observed `drain LOCKED, pending=1` state and prove it cannot cause callback loss/duplication under normal operation

Reuse upstream Desktop Relay launch/recovery mechanisms where possible. Borrow only the minimal proven operational patterns from Commander Plus. Do not rebuild the relay or expand into a general workstation platform.

## Reference-project comparison

### Desktop Relay

Use as the core base. It already provides the remote-MCP termination/session model, shared long-lived Desktop Commander child, authentication, policy/rate limits, audit, retained large results, recovery tooling, launch-agent support, dashboard/file-preview extras, and update/recovery procedures. We currently need no source fork.

### Commander Plus

Do not adopt as the core product. Its relevant reference value is the production wrapper around OpenAI Secure MCP Tunnel: Keychain-backed tunnel credential handling, `connect/status/doctor/autostart` controls, stable launchers, and operational recovery conventions. Borrow only those patterns that materially reduce maintenance.

## Hard constraints

- Do not modify IO Job Hunter for relay productionization.
- Do not alter PMBridge product logic unless a reproducible PMBridge defect is captured first.
- Do not expose a raw public/LAN Desktop Relay listener.
- Do not put live secrets in GitHub, chat, screenshots, shell history, or committed files.
- Do not broaden scope into a general workstation/automation platform.
- Prefer evidence over redesign; patch only real observed defects.

## Completion definition

The project is complete when:

1. Normal startup/recovery requires no routine manual terminal work after login.
2. There is a documented status/repair/rollback path.
3. Restart/reconnect behavior is verified for relay, tunnel-client, and PMBridge callback flow.
4. The observed drain lock state is classified and shown not to threaten callback correctness, or fixed if it is a real defect.
5. Paid Remote Desktop Commander is no longer needed for routine PMBridge operation.
