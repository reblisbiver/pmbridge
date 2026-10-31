# PMBridge Desktop Relay Runbook

This runbook manages the accepted local-only transport without paid Remote Desktop Commander.

## Pinned baseline

- Desktop Relay source: stock upstream commit `b8b64c8e4dc38e6a1e350b7d7a417023e1907535`
- OpenAI tunnel-client: `0.0.19` (`01d67bb4da0d8359b808b4761f8db171ab682cd7`)
- Relay listener: `127.0.0.1:18788` only
- Tunnel health listener: `127.0.0.1:18080` only
- Tunnel ID: configured in the managed profile; do not paste runtime credentials into this document

## One-time setup

1. Generate the PMBridge-owned runtime config from the already-proven stock runtime:

   ```text
   pmbridge relay configure \
     --source-config /path/to/desktop-relay/spike-config.json \
     --tunnel-binary /path/to/tunnel-client \
     --profile relay-http \
     --profile-dir /path/to/tunnel-client-profiles \
     --home ~/.pmbridge \
     --json
   ```

   The generated profile is a mode-`0600` PMBridge-owned copy. Its control-plane key reference is `env:CONTROL_PLANE_API_KEY`; the upstream profile is not modified.

2. Store the control-plane runtime key in Keychain. The `security` command prompts for the value; do not append the value to the command:

   ```text
   /usr/bin/security add-generic-password -a "$USER" -s pmbridge.control-plane-api-key -w
   ```

3. Store the Desktop Relay bearer credential in Keychain using the same hidden-prompt pattern:

   ```text
   /usr/bin/security add-generic-password -a "$USER" -s pmbridge.desktop-relay-auth -w
   ```

   The value is the complete `Bearer ...` value expected by the managed tunnel profile. Credentials are read only at process launch and are never written to the plist, shell profile, repository, status output, or runbook.

## Routine operator surface

```text
pmbridge relay status --json
pmbridge relay doctor --json
pmbridge relay start --json
pmbridge relay stop --json
pmbridge relay restart --json
pmbridge relay autostart enable --json
pmbridge relay autostart status --json
pmbridge relay autostart disable --json
```

`start` is idempotent. `stop` only terminates the PMBridge-owned supervisor. `doctor` reports missing Keychain entries and process health without returning their values.

## Recovery

The single `com.pmbridge.relay` LaunchAgent owns the relay and tunnel-client children. It waits for relay loopback readiness before starting the tunnel-client, and restarts the pair with bounded backoff if either child exits. Re-running `start` or `autostart enable` does not create a second supervisor.

For a stuck state:

```text
pmbridge relay doctor --json
pmbridge relay restart --json
pmbridge relay doctor --json
```

Do not manually dispatch a PMBridge worker to test transport recovery. Use one harmless relay call first, then inspect the normal PMBridge state.

## Key rotation

Replace a Keychain item by repeating its `security add-generic-password` command with `-U`, entering the new value at the hidden prompt, then run:

```text
pmbridge relay restart --json
pmbridge relay doctor --json
```

Never put a key in shell history, a plist, a profile file, an issue comment, or a log.

## Rollback

1. Disable and unload the managed agent:

   ```text
   pmbridge relay autostart disable --json
   pmbridge relay stop --json
   ```

2. Return to the last accepted manual configuration using stock Desktop Relay commit `b8b64c8e4dc38e6a1e350b7d7a417023e1907535` and tunnel-client `0.0.19`; keep the existing PMBridge recovery agent enabled.
3. Do not delete the Keychain entries until the rollback has been verified; they contain no repository state and can be removed separately with `security delete-generic-password` if required.

## Drain lock classification

The Issue #5 `pmbridge drain --json -> LOCKED, delivered=0, pending=2` result was local lock contention: another drain invocation held `event-drain.lock`. The tested worker callback was seen exactly once, with no duplicate dispatch or callback loss. A separate reproducible `UI_BUSY` false positive came from selecting an editable code block instead of the ChatGPT composer; the bounded selector/placeholder fix is covered by regression tests. No PMBridge dispatch, deduplication, or callback semantics were changed. See `docs/acceptance/issue5-drain-classification.md`.
