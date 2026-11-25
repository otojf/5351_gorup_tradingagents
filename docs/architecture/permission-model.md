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
| `src/tradingagents/**`, `src/cli/**`, `src/fr_b2/**` | R | R+W | R |
| `test/**`, `src/eval/**`, `scripts/ci/**` | R | R+W | R |
| `docs/**` (other), `transcripts/**` | R | R+W | R |
| `prompts/**` | R | R | R |
| `pyproject.toml` | R | R+W (dependency changes need review) | R |
| `.github/workflows/**` | R | R (W only with team approval) | R |
| `AGENTS.md`, `Prompt.md`, `.opencode/rules.md`, `.agent/rules.md` | R | **–** (human-only) | R |
| `.env*`, secrets, credentials | **–** | **–** | **–** |
| `CHANGELOG.md`, `LICENSE`, `assets/**` | R | R | R |

## 3. Guard rules

- Human-only files cannot be written by any agent role; a change requires an
  architecture decision (ADR) and human approval.
- Secrets are never read or written. A command that would read `.env*` is denied.
- Safety-critical paths (`src/tradingagents/agents/rating.py`,
  `src/tradingagents/risk_gate/**`, `src/tradingagents/graph/**`) require an
  approving human review before merge. The budget cap is not implemented
  (NFR-C1 is partial), so no budget path exists yet.
- The verifier role never edits source; it only reports.

## 4. Enforcement

- `.opencode/permissions.jsonc` declares the whitelist for the coding agent.
- Branch protection + gate 1 (test-approval) + gate 6 (AI-use log) enforce the
  human gates in CI.
- `docs/review-memo.md` records the human review for safety-critical changes.

## 5. Enforcement check

- `scripts/ci/check_permissions.py` (part of gate 2) parses
  `.opencode/permissions.jsonc` and verifies that every whitelisted path pattern
  resolves to a tracked path, that the human-only files are read-only, and that
  the safety-critical paths carry the architecture-decision guard. It is a
  structural check, not a substitute for the human review recorded in
  `docs/review-memo.md`.
