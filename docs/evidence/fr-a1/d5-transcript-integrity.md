# FR-A1 D5 — Session Transcript Integrity

The course requires a **full raw AI coding-agent session transcript with human
annotations**. This document identifies where the raw records actually live and how
to preserve them. It does **not** contain a synthetic transcript, and it does **not**
claim the D5 submission is complete unless the raw export below has been produced.

## Where the raw OpenCode session records live

OpenCode stores sessions locally in a SQLite database and accompanying logs:

- Database: `~/.local/share/opencode/opencode.db`
  - Tables relevant to a transcript: `session`, `message`, `part`
    (`part` holds the JSON `data` for each message part — text, tool calls, tool
    results, reasoning, etc.),
  - plus `session_message` linking messages to sessions.
- Runtime log: `~/.local/share/opencode/log/opencode.log` (the active file observed
  was `opencode.log`, ~2 MB at the time of this review).
- Snapshots: `~/.local/share/opencode/snapshot/`.

Raw sessions observed in the database for this work (read-only query at this
review):

| Session id | Title | Recorded messages |
|---|---|---|
| `ses_e370b0736ffeCmg7sOktmZ` | FR-A1 Deterministic Risk Gate 设计与测试计划 | 458 |
| `ses_e372492e6ffe7GI2ddI30U` | FR-A1 风险闸门只读可行性与实施计划 | 29 |

The large session is the extended FR-A1 design → test → implementation → review →
evidence session; the smaller one covers the earlier read-only feasibility planning.

## How to preserve the raw transcript (do this before it ages out)

1. **Stop writing** to the DB for the sessions to export (pause the agent), or copy
   the DB and its `-wal`/`-shm` sidecars together for a consistent snapshot:
   `cp opencode.db opencode.db-wal opencode.db-shm <dest>/`.
2. **Export the raw session** (messages + parts, end to end, no summarizing) to
   JSONL. A safe read-only recipe:

   ```bash
   python - <<'PY' > fr-a1-raw-transcript.jsonl
   import sqlite3, os, json
   p = os.path.expanduser("~/.local/share/opencode/opencode.db")
   con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
   sid = "ses_e370b0736ffeCmg7sOktmZ"   # and/or ses_e372492e6ffe7GI2ddI30U
   for mid, ts, data in con.execute(
       "select id, time_created, data from message where session_id=? order by time_created, id", (sid,)):
       print(json.dumps({"type": "message", "id": mid, "time": ts, "data": json.loads(data)}, ensure_ascii=False))
       for pid, pts, pdata in con.execute(
           "select id, time_created, data from part where message_id=? order by time_created, id", (mid,)):
           print(json.dumps({"type": "part", "id": pid, "time": pts, "data": json.loads(pdata)}, ensure_ascii=False))
   con.close()
   PY
   ```

   Repeat for the second session id if both are to be included. Do not edit or
   truncate the exported parts; the requirement is the *raw* transcript.
3. **Preserve the runtime log** in parallel (`cp ~/.local/share/opencode/log/opencode.log
   <dest>/opencode.log`) as corroborating evidence.
4. Keep the raw export and the log read-only; add human annotations as a **separate**
   layer (below), not by editing the raw file.

## Human annotation outline (to attach alongside the raw export)

Annotate by session/message reference; do not rewrite the transcript. Suggested
anchors, matching the actual approval gates in this work:

1. Requirements classification + architecture candidates (risk engine vs adapter).
2. Test-plan approval and fixture corrections (portfolio consistency; blacklist
   must target the analyzed ticker; directed 100-fixture set).
3. Pre-implementation RED evidence required; core engine implementation approval.
4. Core safety-edge review → RED tests → approved fixes (BUG-001..003).
5. Stage 2 output-boundary architecture approval; CLI vs Python-API config decision.
6. Audit-before-publication ADR revision; two final safety fixes approved.
7. Evidence packaging (this folder); note that D5 must use the raw export, not
   these summaries.

## Integrity statement

These markdown summaries (`contribution-summary.md`, `human-review-milestones.md`)
are **derived** aids for the human, not the D5 deliverable. The D5 deliverable is the
raw JSONL export produced by the recipe above, plus the human's annotations. Until
that export is generated and attached, the D5 transcript should be treated as
**not yet complete**.
