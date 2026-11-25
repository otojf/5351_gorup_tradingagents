# MCP / Tool Manifest (D3)

The tools the coding agent may call, and which roles may call them. This project
does not yet use a dedicated MCP server; this manifest records the tool surface
the agent is permitted to use and the role boundaries.

## 1. Agent tool surface

| Tool | Purpose | Allowed roles |
|---|---|---|
| Read / Glob / Grep | Inspect files | all roles |
| Edit / Write | Change files | build role, only within `AGENTS.md` §4 "modifiable" paths |
| Bash | Run tests, lint, gates, git (read-only except explicit approved commits) | build + verification roles |
| `pytest`, `ruff`, `scripts/ci/*` | Verify | verification role |

## 2. Denied by default

- Reading or writing `.env*`, secrets, credentials.
- Editing human-only files (`AGENTS.md`, `Prompt.md`, `.opencode/rules.md`,
  `.agent/rules.md`, `architecture-blueprint.md`) without an architecture
  decision.
- Network calls from tests (tests are offline; live tests use the `integration`
  marker and are excluded by default).
- Wiring branch protection or pushing without explicit human instruction.

## 3. Role → path matrix

See `.opencode/permissions.jsonc` for the machine-readable version. Default is no
read, no write; every path is explicitly whitelisted.

## 4. Status

- No dedicated MCP server is used. The tool surface above is the OpenCode
  built-in tool set; permissions and guard rules live in
  `.opencode/permissions.jsonc` and are checked by
  `scripts/ci/check_permissions.py` in gate 2. If an MCP server is introduced,
  list its tools, scopes, and allowed roles here and mirror them in the
  permission model.
