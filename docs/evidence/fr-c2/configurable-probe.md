# FR-C2 configurable/checkpoint 最小技术验证

- 日期：2026-11-17
- 阶段：技术验证（probe），**未实现跳过功能，未修改生产代码**
- 新增文件：`tests/test_fr_c2_probe.py`（仅测试用探针）
- 数据/模型：全部模拟（`ScriptedModel`/测试工具），不读取任何真实凭据，不联网
- 跳过日志：本阶段**不**验证“一条跳过日志”（功能尚不存在）

## 实际依赖版本

由临时 venv 安装 `-e .` 得到（本次运行环境）：

| 包 | 版本 |
|---|---|
| Python | 3.14.4 |
| langgraph | 1.2.22 |
| langgraph-checkpoint-sqlite | 3.1.3 |
| langchain-core | 1.8.1 |
| pandas | 3.1.1 |
| pytest | 9.2.0 |
| tradingagents（本仓库） | 0.7.1 |

## 探针目标

1. 带 `Lock`/`Event` 的对象能经图 `RunnableConfig.configurable` 传到真实工具调用。
2. checkpoint 写入、读取正常。
3. 检查持久化内容（config / metadata / channel_values / pending_writes / 原始 SQLite 表），不只检查图 state。
4. 新运行使用新对象，不复用旧运行状态。
5. 工具发生模拟数据源异常时，checkpoint 仍能正常写入、读回。
6. 同一 checkpoint thread 中断后**真正恢复执行**，传入新的运行对象，工具收到新对象（非旧对象）。

## 环境准备

系统 Python 无 `langgraph`，故在临时 venv 安装项目依赖（不污染仓库）：

```bash
cd /tmp/opencode
python3 -m venv fr-c2-venv
cd /mnt/c/Users/R/Documents/Codex/2026-11-05/ban/work/team-fr-c2-opencode
/tmp/opencode/fr-c2-venv/bin/python -m pip install -q --disable-pip-version-check -e . pytest
/tmp/opencode/fr-c2-venv/bin/python -m pip install -q ruff
```

依赖确认：

```bash
/tmp/opencode/fr-c2-venv/bin/python -c "import langgraph, langgraph.checkpoint.sqlite, langchain_core, pytest, pandas; import tradingagents; print('ok', tradingagents.__version__)"
# 输出: ok 0.7.1
```

## 探针设计要点

- `RunProbe`：运行级对象，携带 `threading.Lock`、`threading.Event`，模拟将来的 `RunSkipState`。
- `probe_tool`：测试专用工具，签名 `(text: str, config: RunnableConfig)`，从
  `config["configurable"]["fr_probe_object"]` 取对象；工具能否拿到 config 是本次验证核心。
  （注：`config` 参数必须注解为 `RunnableConfig`，否则会被当作必填字段校验而报
  `config: Field required`。）
- `_drive_run`：标准 `StateGraph` + `ToolNode([probe_tool])`，用真实 `SqliteSaver` 持久化，
  以 `thread_id` 区分 Run A / Run B。
- 深度持久化检查：既遍历 `saver.list()` 的 `CheckpointTuple`，也直接查询底层 SQLite 的
  `checkpoints`、`writes` 原始行。
- 第二探针：复现真实分析师所用节点形状 `ToolNode(list(spec.tools))`
  （见 `tradingagents/graph/setup.py:_analyst_graph`），验证 configurable 到工具。
- 第三探针（异常）：工具内抛 `BoomError`（模拟数据源异常），验证 checkpoint 仍写入且可读回。
- 第四探针（真实恢复）：同一 `thread_id` 首次运行中途抛异常留下 checkpoint，随后以
  `invoke(None)` **继续同一 thread**（真正的中断恢复），并传入**新的** `RunProbe`。

> 注：第四探针不是“两个不同 thread 各跑一次”。它复用**同一个** `thread_id`，第一次以
> 输入 `{"messages": []}` 运行并在工具处中断，第二次以输入 `None` 让 LangGraph 从该
> checkpoint 继续。

## 实际结果

命令：

```bash
/tmp/opencode/fr-c2-venv/bin/python -m pytest tests/test_fr_c2_probe.py -q -s
```

结果：`4 passed in ~1.8s`。关键输出：

### 探针 1：对象传递 + checkpoint 持久化

```json
{
  "tool_text_A": "PROBE_OK tag=run-A text=hello",
  "object_reached_tool": true,
  "checkpoint_tuple_count": 4,
  "checkpoint_keys": ["channel_values","channel_versions","id","ts","updated_channels","v","versions_seen"],
  "channel_values_repr": "{'messages': [ToolMessage(content='PROBE_OK tag=run-A text=hello', name='probe_tool', tool_call_id='c1')]}",
  "metadata_repr": "{'source': 'loop', 'step': 2, 'parents': {}}",
  "config_repr": "{'configurable': {'thread_id': 'probe-A', 'checkpoint_ns': '', 'checkpoint_id': '...'}}",
  "pending_writes_repr": "[]",
  "persisted_mentions_object_key": false,
  "persisted_mentions_class_or_lock": false,
  "tool_text_B": "PROBE_OK tag=run-B text=hello",
  "object_B_reached_tool": true,
  "objects_distinct": true,
  "sqlite_tables": ["checkpoints","writes"],
  "raw_sqlite_mentions_object_key": false,
  "raw_sqlite_mentions_class_or_lock": false,
  "checkpoint_readback_ok": true
}
```

观察：

- 工具 A 实际收到对象（`object_reached_tool: true`），返回含 `run-A`。
- 持久化的 `config` 只含 `thread_id`/`checkpoint_ns`/`checkpoint_id`，**不含** `fr_probe_object`。
- `metadata` 只有 `source`/`step`/`parents`；`channel_values` 只有 `messages`。
- 原始 SQLite 的 `checkpoints`、`writes` 表均**不含**对象键、`RunProbe`、`Lock`。
- 新运行 B 的对象与 A 不同（`objects_distinct: true`），各自只记录到自己的 id。

### 探针 2：真实分析师 ToolNode 形状

```json
{
  "tool_text": "REAL_PROBE_OK tag=analyst-node",
  "tool_saw_object": true,
  "seen_ids": [137730987029072],
  "expected_id": 137730987029072
}
```

观察：以 `ToolNode(list(spec.tools))`（真实分析师构建方式）驱动时，工具同样收到
`configurable` 里的运行对象。

### 探针 3：工具抛异常时 checkpoint 仍写入、可读回

```json
{
  "tool_received_object": true,
  "exception_propagated": true,
  "checkpoint_tuple_count_after_error": 3,
  "checkpoint_readback_ok": true,
  "checkpoint_state_repr": {
    "messages": [
      "content='' ... tool_calls=[{'name': 'boom_tool', 'args': {'text': 'x'}, 'id': 'c1', 'type': 'tool_call'}] ..."
    ],
    "branch:to:tools": null
  },
  "persisted_mentions_object_key": false,
  "persisted_mentions_class_or_lock": false
}
```

观察：

- 工具在抛异常前收到了运行对象（`tool_received_object: true`）。
- 模拟数据源异常向外传播（`exception_propagated: true`），运行未被伪装成成功。
- 异常发生后，checkpoint 仍有 3 条元组且 `get_tuple` 可读回（`checkpoint_readback_ok: true`）；
  说明“执行前写 checkpoint”的语义保留，异常不会抹掉已有检查点。
- 持久化内容中依然没有运行对象键、类名或锁。

### 探针 4：同一 thread 真实中断后恢复，工具收到新对象

```json
{
  "interrupted_first_run": true,
  "old_object_seen_ids": [127104074138288],
  "new_object_seen_ids": [127104113682352],
  "new_object_id": 127104113682352,
  "old_object_id": 127104074138288,
  "resumed_tool_text": "RESUMED_OK tag=new-run",
  "resume_received_new_object": true,
  "resume_did_not_reuse_old_object": true,
  "objects_distinct": true
}
```

观察：

- 第一次运行在同一 `thread_id` 上于工具处中断（`interrupted_first_run: true`），旧对象到达工具一次。
- 第二次以 `invoke(None)` 继续**同一 thread**，传入**新** `RunProbe`。
- 恢复后的工具收到的是新对象（`resume_received_new_object: true`，`resumed_tool_text` 含
  `tag=new-run`），旧的运行对象没有被恢复或复用（旧 id 只出现在中断的第一次尝试中）。
- 说明运行对象**不随 checkpoint 持久化，也就不会被恢复**；恢复运行由调用方提供新对象。

## Lint

```bash
/tmp/opencode/fr-c2-venv/bin/ruff check tests/test_fr_c2_probe.py
# All checks passed!
```

## 结论

1. **传递可行**：放在 `RunnableConfig.configurable` 中的 `Lock`/`Event` 承载对象可以到达
   实际工具调用（标准 `ToolNode` 与真实分析师节点形状均验证）。
2. **checkpoint 正常**：写入、`get_tuple` 读取均成功；**工具抛异常时检查点仍写入且可读回**，
   异常照常向外传播。
3. **不被持久化**：`config`、`metadata`、`channel_values`、`pending_writes` 及原始 SQLite
   `checkpoints`/`writes` 表均未出现该对象、其类名或锁；`configurable` 里的运行对象未进入检查点。
4. **运行隔离**：每次运行使用新对象，Run A / Run B 互不复用状态。
5. **真实恢复仍用新对象**：同一 `thread_id` 中断后以 `invoke(None)` 恢复，工具收到调用方传入的
   **新** 对象，旧对象没有被恢复或复用。

因此，方案 §6 中“`configurable` 不进 checkpoint”的**假设在本探针范围内成立**。这**仅**是
对该假设的技术验证通过，不代表跳过功能已实现，也不改变“一条跳过日志”等尚未实现的行为。

## 局限与后续

- 本探针用的是测试专用工具与最小图，未改动生产工具 `get_macro_indicators`（它尚无
  `config` 参数，属后续实现步骤）。
- 未验证并发首次进入（多 worker 争用 `RunSkipState`），属实现阶段的任务。
- 真实图整图 `propagate` 的端到端探针因工具替换涉及 `ANALYST_NODE_SPECS` 编译期快照，
  未强行驱动；其工具执行路径与探针 2 的 `ToolNode(list(spec.tools))` 相同。
- 本阶段到此停止，不自动切换到完整实现，等待批准。
