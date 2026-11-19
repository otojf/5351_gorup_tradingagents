# Prompt (D9) — Static Launch Instruction

This is the single static prompt the coding agent reads after `AGENTS.md`. It is
the launch instruction. It does **not** run the agent unattended to completion.

## Instruction to the agent

1. **Read first, in this order.** `AGENTS.md`, then this file, then
   `architecture-blueprint.md`, then `docs/architecture/adr/`,
   `docs/architecture/invariants.md`, `docs/architecture/trace-matrix.md`,
   `docs/architecture/runtime-policy-catalog.md`, `docs/req/requirements.yaml`
   (+ `req-schema.json`), `.opencode/rules.md`, `.agent/rules.md`, and the
   `docs/code-governance/` constraints.

2. **Plan before code.** For any non-trivial change, produce an execution plan
   containing:
   - **Traceability** — which requirement ID(s)/invariant(s) this change serves.
   - **Interface contract** — functions/state keys/modules touched, inputs and
     outputs.
   - **Scope boundaries** — what is in scope and explicitly out of scope.
   - **Testing strategy** — the tests that will prove it (including at least one
     negative test per invariant).
   - **Steps** — ordered, each with a verification checkpoint.

3. **Stop for human approval.** Present the plan and **wait**. Do not write code
   before a human approves the plan. This is the plan gate.

4. **Build in approved slices.** Implement one approved slice at a time. Keep the
   baseline: extend `tradingagents/`, `cli/`, `tests/`, `eval/`; never replace
   them. Each new file references the ADR and invariant it implements.

5. **Self-verify, then stop again.** Run the tests and the six gates locally
   (`pytest -q`, `ruff check .`, and the `scripts/ci/` gates). Report results
   honestly, including failures and uncovered checks. **Stop for human review**
   at each stage boundary (test approval, implementation, verification,
   architecture revision on evidence).

6. **Never** weaken or delete a test to make a gate pass. **Never** read or
   commit secrets. **Never** edit human-only files (`AGENTS.md`, `Prompt.md`,
   `.opencode/rules.md`, `.agent/rules.md`, `architecture-blueprint.md`) without
   an architecture decision.

## Human gates at every stage

| Stage | Human gate |
|---|---|
| Requirements classification | approve the requirements |
| Architecture candidates | approve the chosen architecture (ADR) |
| Test plan | approve tests before implementation (gate 1) |
| Implementation | approve starting code |
| Verification | review gate results and evidence |
| Architecture revision | approve changes based on test evidence |

This prompt is the launch instruction only; the agent proceeds through build and
self-verification with the human gates above, and does not run unattended.
