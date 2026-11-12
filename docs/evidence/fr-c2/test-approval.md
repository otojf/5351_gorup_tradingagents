# FR-C2 test approval

- approved_by: The user in this Codex chat (name and student ID not supplied)
- approved_date: 2026-11-12
- test_scope: Missing FRED credentials; repeated/same and different indicators; one skip event per supplier per run; zero supplier/HTTP calls after preflight; subsequent-run recovery; concurrent-run isolation; concurrent calls in one run; normal/debug/streamed full-graph completion; existing fallback regressions.

Before implementation the assistant presented the scope, file boundaries and
six acceptance scenarios. The user replied: "好的，可以去执行了".
This records that approval, not an invented teammate review or a merge approval.

Tests were added before production changes. The earlier read-only reproduction
at main 46bde74 found that seven sequential missing-key router calls entered
FRED seven times, performed zero HTTP calls and emitted fourteen warning events.
This was a synthetic function-level reproduction, not seven HTTP retries or a
measured live-model run. No full raw chat export is included in this record.

Human code review and any course-specific OpenCode evidence remain separate.
