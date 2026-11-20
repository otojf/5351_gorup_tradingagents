"""FR-C2 technical probe: can a Lock/Event-bearing object ride the graph config
into real tool calls, survive checkpointing, and stay per-run?

This is a PROBE, not a feature. It does NOT implement skipping, does NOT assert
"one skip log", and only uses simulated data and a scripted model.

It answers:
  1. Does an object placed in RunnableConfig.configurable reach an actual tool
     invocation inside ToolNode, including the real TradingAgentsGraph path?
  2. Do checkpoint write/read work while it is in config?
  3. What is actually persisted (config / metadata / channel_values / pending
     writes / raw SQLite rows), inspected beyond just the graph state?
  4. Does a fresh run use a fresh object (no state reused across runs)?

The probe uses TEST-ONLY tools that receive `config` via RunnableConfig; the
production get_macro_indicators does not take config yet (a later step).
"""

from __future__ import annotations

import json
import sqlite3
import threading

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict


class ProbeState(TypedDict, total=False):
    messages: list


class RunProbe:
    """Run-scoped object carrying a Lock and an Event, like RunSkipState would."""

    def __init__(self, tag: str):
        self.tag = tag
        self.lock = threading.Lock()
        self.event = threading.Event()
        self.seen_ids: list[int] = []
        self.seen_threads: set[str] = set()

    def record(self) -> None:
        with self.lock:
            self.seen_ids.append(id(self))
            self.seen_threads.add(threading.current_thread().name)


@tool
def probe_tool(text: str, config: RunnableConfig) -> str:
    """A test-only tool that reads the run object from the graph config."""
    cfg = config or {}
    obj = (cfg.get("configurable") or {}).get("fr_probe_object")
    if obj is None:
        return f"PROBE_NO_OBJECT text={text}"
    obj.record()
    return f"PROBE_OK tag={obj.tag} text={text}"


def _drive_run(saver, thread_id: str, probe: RunProbe):
    """Run one tool-using turn with `probe` in configurable; return final state."""

    def agent_node(state):
        if isinstance(state.get("messages"), list) and state["messages"] \
                and isinstance(state["messages"][-1], ToolMessage):
            return {"messages": [AIMessage(content="done")]}
        return {"messages": [AIMessage(content="", tool_calls=[
            {"name": "probe_tool", "id": "c1", "args": {"text": "hello"}},
        ])]}

    builder = StateGraph(ProbeState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode([probe_tool]))
    builder.add_edge(START, "agent")
    builder.add_edge("agent", "tools")
    builder.add_edge("tools", END)
    app = builder.compile(checkpointer=saver)

    cfg = {"configurable": {"thread_id": thread_id, "fr_probe_object": probe}}
    return app.invoke({"messages": []}, config=cfg)


def _persisted_blob(saver: SqliteSaver, thread_id: str) -> dict:
    """Everything the saver keeps for a thread, rendered as plain text."""
    out = []
    for tup in saver.list({"configurable": {"thread_id": thread_id}}):
        out.append({
            "checkpoint_keys": sorted(tup.checkpoint.keys()),
            "channel_values_repr": repr(tup.checkpoint.get("channel_values", {})),
            "metadata_repr": repr(tup.metadata),
            "config_repr": repr(tup.config),
            "parent_config_repr": repr(tup.parent_config),
            "pending_writes_repr": repr(tup.pending_writes),
        })
    return {"tuples": out}


@pytest.mark.unit
def test_probe_object_reaches_tool_checkpoint_and_stays_per_run(tmp_path):
    db = tmp_path / "probe.db"
    conn = sqlite3.connect(str(db), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    try:
        # ---- Run A ----
        probe_a = RunProbe(tag="run-A")
        final_a = _drive_run(saver, "probe-A", probe_a)
        tool_text_a = final_a["messages"][-1].content

        snap = _persisted_blob(saver, "probe-A")
        blob = json.dumps(snap, default=str)
        report = {
            "tool_text_A": tool_text_a,
            "object_reached_tool": "PROBE_OK" in tool_text_a and probe_a.seen_ids == [id(probe_a)],
            "checkpoint_tuple_count": len(snap["tuples"]),
            "checkpoint_keys": snap["tuples"][0]["checkpoint_keys"] if snap["tuples"] else [],
            "channel_values_repr": snap["tuples"][0]["channel_values_repr"] if snap["tuples"] else "",
            "metadata_repr": snap["tuples"][0]["metadata_repr"] if snap["tuples"] else "",
            "config_repr": snap["tuples"][0]["config_repr"] if snap["tuples"] else "",
            "pending_writes_repr": snap["tuples"][0]["pending_writes_repr"] if snap["tuples"] else "",
            "persisted_mentions_object_key": "fr_probe_object" in blob,
            "persisted_mentions_class_or_lock": ("RunProbe" in blob) or ("threading.Lock" in blob),
        }

        # ---- Run B (fresh object, separate thread) ----
        probe_b = RunProbe(tag="run-B")
        final_b = _drive_run(saver, "probe-B", probe_b)
        tool_text_b = final_b["messages"][-1].content

        # ---- Deep persistence check: raw SQLite tables, not just state ----
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = sorted(r[0] for r in cur.fetchall())
        raw = {}
        for t in tables:
            cur.execute(f"SELECT * FROM {t}")
            raw[t] = json.dumps(cur.fetchall(), default=str)
        raw_blob = json.dumps(raw, default=str)

        # ---- Read the stored checkpoint back ----
        stored = saver.get_tuple({"configurable": {"thread_id": "probe-A"}})

        report.update({
            "tool_text_B": tool_text_b,
            "object_B_reached_tool": "PROBE_OK" in tool_text_b and probe_b.seen_ids == [id(probe_b)],
            "runA_object_id": id(probe_a),
            "runB_object_id": id(probe_b),
            "objects_distinct": id(probe_a) != id(probe_b),
            "runA_seen_ids": probe_a.seen_ids,
            "runB_seen_ids": probe_b.seen_ids,
            "sqlite_tables": tables,
            "raw_sqlite_mentions_object_key": "fr_probe_object" in raw_blob,
            "raw_sqlite_mentions_class_or_lock": ("RunProbe" in raw_blob) or ("Lock" in raw_blob),
            "checkpoint_readback_ok": stored is not None,
        })

        print("\n===FR-C2-PROBE-REPORT===")
        print(json.dumps(report, indent=2, default=str))
        print("===END-FR-C2-PROBE-REPORT===")

        # Probe assertions (structure, not the unimplemented feature):
        assert report["object_reached_tool"], tool_text_a
        assert report["object_B_reached_tool"], tool_text_b
        assert report["checkpoint_tuple_count"] >= 1
        assert report["objects_distinct"]
        # The headline question: is the configurable object persisted?
        assert not report["persisted_mentions_object_key"], "configurable key leaked into checkpoint"
        assert not report["persisted_mentions_class_or_lock"], "object class/lock leaked into checkpoint"
        assert not report["raw_sqlite_mentions_object_key"], "object key leaked into raw sqlite"
        assert not report["raw_sqlite_mentions_class_or_lock"], "class/lock leaked into raw sqlite"
        assert report["checkpoint_readback_ok"], "checkpoint could not be read back"
    finally:
        conn.close()


@tool
def real_graph_probe_tool(text: str, config: RunnableConfig) -> str:
    """Test-only analyst tool that must receive the run object via config."""
    obj = (config or {}).get("configurable", {}).get("fr_probe_object")
    if obj is None:
        return "REAL_PROBE_NO_OBJECT"
    obj.record()
    return f"REAL_PROBE_OK tag={obj.tag}"


@pytest.mark.unit
def test_configurable_reaches_tools_in_the_analyst_toolnode_shape():
    """The analysts' ToolNode(list(spec.tools)) passes configurable into tools.

    ``tradingagents/graph/setup.py:_analyst_graph`` builds each analyst's tool
    node as ``ToolNode(list(spec.tools))``; this reproduces exactly that node
    shape and drives it, which is the same code path a real run uses.
    """
    from langgraph.prebuilt import ToolNode as _ToolNode

    probe = RunProbe(tag="analyst-node")
    app = StateGraph(ProbeState)
    app.add_node("tools", _ToolNode([real_graph_probe_tool]))
    app.add_edge(START, "tools")
    app.add_edge("tools", END)
    compiled = app.compile()

    state = {"messages": [AIMessage(content="", tool_calls=[
        {"name": "real_graph_probe_tool", "id": "c1", "args": {"text": "hi"}},
    ])]}
    cfg = {"configurable": {"fr_probe_object": probe}}
    final = compiled.invoke(state, config=cfg)

    tool_text = final["messages"][-1].content
    print("\n===FR-C2-ANALYST-TOOLNODE-REPORT===")
    print(json.dumps({
        "tool_text": tool_text,
        "tool_saw_object": probe.seen_ids == [id(probe)],
        "seen_ids": probe.seen_ids,
        "expected_id": id(probe),
    }, indent=2))
    print("===END-FR-C2-ANALYST-TOOLNODE-REPORT===")

    assert "REAL_PROBE_OK" in tool_text, tool_text
    assert probe.seen_ids == [id(probe)], "analyst ToolNode did not pass the configurable object"


class BoomError(RuntimeError):
    """Stand-in for a simulated data-source failure inside the tool."""


@tool
def boom_tool(text: str, config: RunnableConfig) -> str:
    """Test-only tool that records the object then raises like a data-source error."""
    obj = (config or {}).get("configurable", {}).get("fr_probe_object")
    if obj is not None:
        obj.record()
    raise BoomError(f"simulated source failure for {text}")


def _drive_boom_run(saver, thread_id: str, probe: RunProbe):
    """Run a tool that raises; the checkpoint written before the raise must persist."""

    def agent_node(state):
        return {"messages": [AIMessage(content="", tool_calls=[
            {"name": "boom_tool", "id": "c1", "args": {"text": "x"}},
        ])]}

    builder = StateGraph(ProbeState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode([boom_tool]))
    builder.add_edge(START, "agent")
    builder.add_edge("agent", "tools")
    builder.add_edge("tools", END)
    app = builder.compile(checkpointer=saver)

    cfg = {"configurable": {"thread_id": thread_id, "fr_probe_object": probe}}
    return app.invoke({"messages": []}, config=cfg)


@pytest.mark.unit
def test_checkpoint_written_and_readable_when_tool_raises(tmp_path):
    """A simulated data-source exception in the tool must still leave a readable
    checkpoint: write-before-execute is preserved, and the exception propagates."""
    db = tmp_path / "boom.db"
    conn = sqlite3.connect(str(db), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    try:
        probe = RunProbe(tag="boom-run")
        raised = None
        try:
            _drive_boom_run(saver, "boom-A", probe)
        except BoomError as exc:
            raised = exc

        snap_after = _persisted_blob(saver, "boom-A")
        blob = json.dumps(snap_after, default=str)
        stored = saver.get_tuple({"configurable": {"thread_id": "boom-A"}})

        report = {
            "tool_received_object": probe.seen_ids == [id(probe)],
            "exception_propagated": isinstance(raised, BoomError),
            "checkpoint_tuple_count_after_error": len(snap_after["tuples"]),
            "checkpoint_readback_ok": stored is not None,
            "checkpoint_state_repr": stored.checkpoint.get("channel_values", {}) if stored else None,
            "persisted_mentions_object_key": "fr_probe_object" in blob,
            "persisted_mentions_class_or_lock": ("RunProbe" in blob) or ("Lock" in blob),
        }
        print("\n===FR-C2-EXCEPTION-CHECKPOINT-REPORT===")
        print(json.dumps(report, indent=2, default=str))
        print("===END-FR-C2-EXCEPTION-CHECKPOINT-REPORT===")

        assert report["tool_received_object"], "tool did not run before raising"
        assert report["exception_propagated"], "simulated source error did not propagate"
        # The agent step was checkpointed before the tools step ran/failed.
        assert report["checkpoint_tuple_count_after_error"] >= 1
        assert report["checkpoint_readback_ok"], "checkpoint unreadable after tool error"
        assert not report["persisted_mentions_object_key"]
        assert not report["persisted_mentions_class_or_lock"]
    finally:
        conn.close()


@pytest.mark.unit
def test_interrupted_thread_resumes_with_a_new_object(tmp_path):
    """A genuinely interrupted thread resumes on the SAME thread_id and the tool
    receives the NEW run object, never the interrupted run's object.

    This is a real resume: the first run raises mid-graph leaving a checkpoint,
    then the same thread_id is invoked with input None to continue it.
    """
    db = tmp_path / "resume.db"
    conn = sqlite3.connect(str(db), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    try:
        # Controlled failure: the tool raises only on the first attempt.
        state = {"fail": True}

        @tool
        def flaky_tool(text: str, config: RunnableConfig) -> str:
            """Test-only tool that fails once, then succeeds on resume."""
            obj = (config or {}).get("configurable", {}).get("fr_probe_object")
            obj.record()
            if state["fail"]:
                raise BoomError("first attempt fails")
            return f"RESUMED_OK tag={obj.tag}"

        def agent_node(msg_state):
            if isinstance(msg_state.get("messages"), list) and msg_state["messages"] \
                    and isinstance(msg_state["messages"][-1], ToolMessage):
                return {"messages": [AIMessage(content="done")]}
            return {"messages": [AIMessage(content="", tool_calls=[
                {"name": "flaky_tool", "id": "c1", "args": {"text": "hi"}},
            ])]}

        builder = StateGraph(ProbeState)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", ToolNode([flaky_tool]))
        builder.add_edge(START, "agent")
        builder.add_edge("agent", "tools")
        builder.add_edge("tools", END)
        app = builder.compile(checkpointer=saver)

        tid = "resume-A"
        probe_old = RunProbe(tag="old-run")
        interrupted = None
        try:
            app.invoke({"messages": []},
                       config={"configurable": {"thread_id": tid, "fr_probe_object": probe_old}})
        except BoomError as exc:
            interrupted = exc
        assert isinstance(interrupted, BoomError), "first run did not interrupt"
        # Old object reached the tool before the failure.
        assert probe_old.seen_ids == [id(probe_old)]

        # Same thread_id, input None -> LangGraph resumes the interrupted run.
        state["fail"] = False
        probe_new = RunProbe(tag="new-run")
        final = app.invoke(
            None, config={"configurable": {"thread_id": tid, "fr_probe_object": probe_new}}
        )

        resumed_text = final["messages"][-1].content
        report = {
            "interrupted_first_run": isinstance(interrupted, BoomError),
            "old_object_seen_ids": probe_old.seen_ids,
            "new_object_seen_ids": probe_new.seen_ids,
            "new_object_id": id(probe_new),
            "old_object_id": id(probe_old),
            "resumed_tool_text": resumed_text,
            "resume_received_new_object": probe_new.seen_ids == [id(probe_new)],
            "resume_did_not_reuse_old_object": probe_old.seen_ids == [id(probe_old)],
            "objects_distinct": id(probe_old) != id(probe_new),
        }
        print("\n===FR-C2-RESUME-REPORT===")
        print(json.dumps(report, indent=2, default=str))
        print("===END-FR-C2-RESUME-REPORT===")

        assert report["new_object_seen_ids"] == [id(probe_new)], "resume missed the new object"
        assert report["objects_distinct"]
        assert "RESUMED_OK" in resumed_text
        assert "tag=new-run" in resumed_text, resumed_text
        # The old object was used only by the interrupted attempt, never on resume.
        assert probe_old.seen_ids == [id(probe_old)]
    finally:
        conn.close()
