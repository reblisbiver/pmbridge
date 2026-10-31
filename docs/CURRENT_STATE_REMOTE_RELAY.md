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
- WIP=1 for acceptance/productionization tasks.

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

All eight acceptance cases passed:

1. ChatGPT connection/tool discovery.
2. Harmless command execution.
3. Filesystem read.
4. 60+ second long-running command without replay.
5. Large result paging and exact recovery.
6. Process start/inspect/terminate lifecycle.
7. Desktop Commander child kill/recovery through the new path.
8. Unauthorized/invalid requests rejected while the relay remained loopback-only.

Additional manual recheck in a later ChatGPT turn returned exact stdout for:

`printf 'manual-test-ok\n'`

No Cloudflare hostname, public DNS, LAN listener, or paid Remote Desktop Commander transport was required.

## Current implemented state

- Desktop Relay is reachable at loopback only.
- Secure MCP Tunnel is functional.
- `openai/tunnel-client v0.0.19` is functional.
- Relay upstream is running.
- ChatGPT app `PMBridge Desktop Relay` is connected and callable.
- Credentials were kept out of chat/GitHub evidence; runtime key stored locally with restricted file permissions during acceptance.
- No upstream Desktop Relay source modification is required for the proven path.

## Remaining work

### Phase 1 — PMBridge production acceptance

Goal: prove the real PM workload over the new path, not just generic Desktop Commander operations.

Required lifecycle:

`pm_context inspect -> relay/check -> dispatch_role -> Codex worker -> callback -> inspect result`

Acceptance rule: one disposable, non-product-destructive worker lifecycle completes entirely through `PMBridge Desktop Relay`, with the callback/result verified and no use of the paid Remote Desktop Commander transport.

If this passes, the new transport is accepted for IO Job Hunter / PMBridge production use.

### Phase 2 — zero-touch productionization

Goal: make normal use operationally boring.

Desired operator surface, inspired by the mature production wrapper in Commander Plus but without copying its unrelated feature set:

- status / doctor
- start / stop / restart
- autostart enable / status / disable
- secure runtime-key storage (prefer macOS Keychain if practical)
- launchd startup for relay + tunnel-client
- crash/reconnect recovery
- pinned known-good upstream/runtime versions
- simple rollback/update procedure
- one-page recovery/runbook

Do not build this layer until Phase 1 passes. Reuse upstream Desktop Relay launch/recovery mechanisms where possible and copy/adapt only the minimum proven patterns needed from existing projects.

## Reference-project comparison

### Desktop Relay

Use as the core base. It already provides the remote-MCP termination/session model, shared long-lived Desktop Commander child, authentication, policy/rate limits, audit, retained large results, recovery tooling, launch-agent support, dashboard/file-preview extras, and update/recovery procedures. We currently need no source fork.

### Commander Plus

Do not adopt as the core product. It is a much larger local AI workstation/control plane with many capabilities outside scope. Its relevant reference value is the production wrapper around OpenAI Secure MCP Tunnel: Keychain-backed tunnel credential handling, `connect/status/doctor/autostart` controls, and stable launchers. Borrow only those operational patterns if they materially reduce maintenance.

## Hard constraints

- Do not modify IO Job Hunter merely to make relay acceptance pass.
- Do not modify PMBridge product logic merely to make relay acceptance pass.
- Do not expose a raw public/LAN Desktop Relay listener.
- Do not put live secrets in GitHub, chat, screenshots, or committed files.
- Do not broaden scope into a general workstation/automation platform.
- Prefer evidence over redesign; patch only real observed defects.

## Completion definition

The project is complete when:

1. A full PMBridge worker lifecycle passes over the new transport.
2. Normal startup/recovery requires no routine manual terminal work beyond exceptional maintenance.
3. There is a documented status/repair/rollback path.
4. Paid Remote Desktop Commander is no longer needed for routine PMBridge operation, though it may remain as a temporary fallback until the productionized path has proven stable in normal use.
