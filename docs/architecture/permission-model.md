# Permission Model (D2.6)

File-level read/write rights for each AI coding agent's role. Default is **no
read, no write**; every path is explicitly whitelisted. The machine-readable
version is `.opencode/permissions.jsonc`.

## 1. Roles

| Role | Purpose |
|---|---|
| planner | Reads requirements/architecture; writes plans only (no code). |
| builder | Writes code/tests/docs within whitelisted paths. |
| verifier | Runs tests/gates; reads everything; writes no source. |

## 2. Path rights by role

Legend: R = read, W = write, – = denied (default).

| Path | planner | builder | verifier |
|---|---|---|---|
| `docs/req/**` | R | R | R |
| `docs/architecture/**`, `architecture-blueprint.md` | R | R | R |
| `tradingagents/**`, `cli/**` | R | R+W | R |
| `tests/**`, `eval/**`, `scripts/ci/**` | R | R+W | R |
| `docs/**` (other), `transcripts/**` | R | R+W | R |
| `prompts/**` | R | R | R |
| `.github/workflows/**` | R | R (W only with team approval) | R |
| `AGENTS.md`, `Prompt.md`, `.opencode/rules.md`, `.agent/rules.md` | R | **–** (human-only) | R |
| `.env*`, secrets, credentials | **–** | **–** | **–** |
| `CHANGELOG.md`, `LICENSE`, `assets/**` | R | R | R |

## 3. Guard rules

- Human-only files cannot be written by any agent role; a change requires an
  architecture decision (ADR) and human approval.
- Secrets are never read or written. A command that would read `.env*` is denied.
- Safety-critical paths (`tradingagents/agents/rating.py`, the risk gate, budget
  cap) require an approving human review before merge.
- The verifier role never edits source; it only reports.

## 4. Enforcement

- `.opencode/permissions.jsonc` declares the whitelist for the coding agent.
- Branch protection + gate 1 (test-approval) + gate 6 (AI-use log) enforce the
  human gates in CI.
- `docs/review-memo.md` records the human review for safety-critical changes.

## 5. Known gaps

- TODO (team): no automated permission test yet beyond CI gates; see
  `docs/debt-register.md` (guardrail debt).
