# FR-C2: skip unconfigured suppliers once per run

Baseline: main `46bde74f71af6ca6a92e52a20dad5711af30cd67`.
Feature branch: `feat/fr-c2-vendor-skip`.

## Behavior and scope

Preflight FRED credentials in the supplier router during an analysis. Missing,
empty or whitespace-only keys yield `DATA_UNAVAILABLE`, zero supplier entries,
zero HTTP calls and one `vendor_skipped` warning event per run/supplier. Model
tool-call requests are not HTTP requests and are not claimed to be eliminated.

The structured log event contains event, vendor, method, reason, run_id and a
vendor_skip_count increment of 1. No key value or raw configuration exception
is saved. A fresh analysis rechecks configuration; a key added mid-analysis
only takes effect on the next analysis. Unknown credentials are not remotely
validated. An invalid nonempty key, network error or rate limit is outside
this feature's preflight scope and retains existing routing behavior.

Only FRED has a proactive credential check. Other optional-enrichment vendors
that raise VendorNotConfiguredError can also be remembered for the current run; keyless
vendors are not presumed to require credentials. Explicit fallback chains
still run in order. Core categories still surface errors when no supplier can
serve them, preserving their original configuration-error subtype. Calls made directly outside an analysis/run scope retain legacy
behavior, so callers building their own loops should use vendor_run_scope().

## Architecture decision (FR-C2)

Use a separate ContextVar-bound VendorRunState with a per-object lock. Worker
contexts in one LangGraph run share the object; unrelated runs get different
objects. The lock covers the first skip transition and event, not network I/O.
Ordinary propagate() starts/reset its scope in a finally-backed context manager.
stream_run() initializes/reuses state in its copied context; it does not set
the caller's context across yields. A debug stream reuses its enclosing run.

Rejected: a global disabled-vendor set (leaks across analyses); thread-local
state (breaks tool-worker sharing); putting mutable state in get_config()
(returns deep copies); prompt-only avoidance (does not enforce behavior).

Changes intentionally avoid decision schemas, risk gates, evidence attribution,
evaluation formats, CI settings, shared requirements and teammates' branches.
Public-file overlap remains possible in router.py/trading_graph.py and must be
reviewed before merging; branch isolation does not guarantee conflict-free merges.

## Acceptance and reproduction

Install project dev dependencies in an isolated Python 3.11+ environment, set
PYTHON_DOTENV_DISABLED=1, and use only synthetic credentials for tests:

```sh
python -m pip install -e ".[dev]" -c docs/evidence/fr-c2/test-constraints.txt
python -m pytest -q tests/test_vendor_skip_on_missing_key.py tests/test_fr_c2_graph.py tests/test_fred.py tests/test_vendor_routing.py tests/test_vendor_errors.py tests/test_graph_end_to_end.py tests/test_dataflows_config.py
python -m ruff check .
```

Recorded results and environment limitations: verification.md.

Shared fixtures block Python sockets and curl_cffi for unit tests. The new
full-graph test scripts three macro tool calls in one ToolNode turn and proves
completion in normal, debug and direct-stream modes without entering FRED.

The existing full-graph offline fixture now supplies a synthetic FRED key so
its successful mocked macro path remains tested; missing-key cases remove it.

## Team integration

Do not merge automatically. Review code/test changes and append this task's
AI-use fragment to the shared log when integrating with the E1 branch. This
branch uses Codex, not OpenCode; see session-summary.md for evidence limits.
Do not change shared requirement selections merely to claim this task's slot.
