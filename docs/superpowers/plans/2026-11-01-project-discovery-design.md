# PMBridge Project Discovery Design

## Intent
A replacement ChatGPT PM should discover already-registered PMBridge projects from PMBridge itself before attempting filesystem search.

## Goals
- Add a read-only project registry command.
- Make replacement-PM documentation require registry lookup before takeover.
- Keep existing project config, takeover, handoff, rebind, jobs, and callback semantics unchanged.

## Non-goals
- No fuzzy matching engine in PMBridge yet.
- No repo scanning or auto-import.
- No storage migration.

## Approach
Add `pmbridge projects list --json`, backed only by `~/.pmbridge/projects/*/config.json`. Return compact metadata sufficient for a PM to identify a project: name, repo, active chat URL, binding version/guarded flag, and whether the repo currently exists. Update `CHATGPT_SETUP.md` so new conversations list registered projects first, then call takeover; filesystem search is fallback only when the registry has no plausible project.
