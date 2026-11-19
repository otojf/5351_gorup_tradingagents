# FR-C2 实现与验证记录

- 日期：2026-11-17
- 负责人：RenLongteng（学号 60662195）
- 阶段：实现 + 验证（未提交、未推送、未合并）
- 依据：`docs/req/fr-c2-plan.md`（已审核）
- 数据/模型：全部模拟；不读取真实凭据，不联网
- 未复制其他分支代码；只改 FR-C2 相关文件。

## 环境

| 包 | 版本 |
|---|---|
| Python | 3.14.4 |
| langgraph | 1.2.22 |
| langgraph-checkpoint-sqlite | 3.1.3 |
| langchain-core | 1.8.1 |
| pandas | 3.1.1 |
| pytest | 9.2.0 |
| tradingagents（本仓库） | 0.7.1 |

venv：`/tmp/opencode/fr-c2-venv`（`pip install -e . pytest`）。

---

## 0. 先修正的测试计数错误（实现前）

问题：`_tool_request_counter` 原先把计数放在 **vendor 实现** 内，统计的是“数据源进入次数”，
与“工具请求次数”混淆。

修正：把工具请求计数移到 **进入 router 的位置**——包装 `router.route_to_vendor`（以及
`tradingagents.agents.tools` 里按名导入的绑定），只在 `method == "get_macro_indicators"` 时 +1；
数据源进入次数由独立的 `_install_fred_stub` / 线程安全桩单独计数。两个计数器完全分开。

- 未降低/删除任何断言：多请求路径仍断言 `工具请求 > 1` 且 `数据源进入 == 1`。
- 验证计数器确实分离：手动模拟 3 次 macro 调用，工具请求计数为 3（>1），而数据源进入计数独立。
- 修正后、实现前跑 paths 测试：5 failed，失败均为 `assert 3 == 1`（数据源进入 3 次）与
  `each run enters FRED once; got 6`，而 `requests > 1` 断言已通过——说明“工具请求 >1”和“数据源进入 1”
  是分开判定的。

---

## 1. 生产代码改动

### 新增 `tradingagents/dataflows/vendor_skip.py`

`RunSkipState`（每次运行一个局部对象）：

- `acquire(key)`：在**同一把锁内**同时判定“已跳过 / 首次(winner) / 等待(waiter)”，返回 `(role, slot)`。
  消除“is_skipped→claim”竞态。
- `finish(key, slot, skipped)`：在**锁内**发布结果、登记 `_skipped`（仅当首次）、唤醒等待者；
  返回**是否首次跳过**，用于“每次运行恰好一条跳过日志”。调用方在 `finally` 中调用。
- `wait(slot, timeout)`：等待 winner 结果（True/False，超时 None）。
- 只保存安全原因码（`"<vendor>:not_configured"`），不保存异常或凭据；持有 `threading.Lock/Event`。

### `tradingagents/dataflows/vendors/fred.py`

`get_api_key()`：`api_key = (os.getenv("FRED_API_KEY") or "").strip()`；空串/纯空白均视为未配置，
抛 `FredNotConfiguredError`。**不**在此写跳过日志（日志由 router 单一负责）。

### `tradingagents/dataflows/router.py` — `route_to_vendor(method, *args, state=None, **kwargs)`

- 新增可选 `state`；缺省时惰性建 `RunSkipState()`。
- vendor 循环角色化：
  - `skipped`：不进数据源，记录首个 `VendorNotConfiguredError` 供兜底哨兵，`continue` 下一个 vendor。
  - `waiter`：`state.wait(slot)`；若 winner 判定跳过则 `continue`；否则落入**同一** `try/except` 正常调用。
  - `winner`：进入统一 `try/except`；`finally` 中 `state.finish(...)`，仅首次跳过时写**一条**日志。
- 只有 `VendorNotConfiguredError` 置 `skipped=True`；网络/限流/其他异常**不**登记跳过。
- 跳过 FRED 后**继续遍历 fallback**（`continue`），不裸返回哨兵。
- 兜底 `Optional ... unavailable` 警告在 `skip_seen` 时**不再重复**（避免 router 两处重复）。

### `tradingagents/agents/tools.py` — `get_macro_indicators`

新增 `config: RunnableConfig` 注入；从 `config["configurable"]["fr_skip_state"]` 取运行状态传给
`route_to_vendor(..., state=...)`。取不到时传 `None`（router 建临时对象）。

### `tradingagents/graph/trading_graph.py`

- `_new_skip_state()` / `_attach_skip_state(args, state=None)`：把 `RunSkipState` 放进
  `args["config"]["configurable"]["fr_skip_state"]`；若已存在则**复用**（不重置）。
- `_run_graph`（`propagate` 与 `debug` 共用）：附加新的运行状态。
- `stream_run`（CLI 直接路径）：附加（若缺省）；`debug` 内部调用时已存在则复用。

`configurable` 不进 checkpoint 已由前置探针验证（见 `configurable-probe.md`），运行对象不被持久化/恢复。

---

## 2. 运行的测试与结果

### 命令

```bash
/tmp/opencode/fr-c2-venv/bin/python -m pytest tests/test_fr_c2_acceptance.py tests/test_fr_c2_paths.py -q
/tmp/opencode/fr-c2-venv/bin/python -m pytest tests/test_fr_c2_probe.py tests/test_fred.py \
    tests/test_vendor_routing.py tests/test_vendor_errors.py tests/test_graph_end_to_end.py \
    tests/test_checkpoint_lifecycle.py -q
/tmp/opencode/fr-c2-venv/bin/python -m pytest -q        # 完整离线回归
/tmp/opencode/fr-c2-venv/bin/ruff check <改动文件与测试>
```

### 结果

| 范围 | 结果 |
|---|---|
| 新增验收测试（acceptance + paths，含本轮两条回归） | **22 passed** |
| checkpoint 探针 + 相关现有测试（8 文件合跑） | **81 passed, 8 subtests passed** |
| 完整离线回归 | **1438 passed, 1 skipped, 1 deselected** |
| ruff（改动文件与测试） | **All checks passed!** |

- 完整回归的 1 skipped：`tests/test_bedrock_provider.py` 因可选依赖 `langchain_aws` 未安装
  （环境原因，与本次改动无关）。1 deselected：`-m "not integration"` 默认排除集成测试。
- 未弱化/跳过任何测试。

### 审核复现问题的回归修复（本轮）

**问题 1：等待者超时仍进入数据源。**
- 复现：`test_waiter_timeout_does_not_enter_data_source_and_is_not_skipped`（先行失败：`entered 1`）。
- 修复（`router.py`）：`state.wait(slot)` 返回 `None` 时**不**调用 `impl_func`；改为记录明确诊断
  `Vendor %r unconfirmed ... after waiting`，把 `VendorUnavailableError` 记为 `last_unavailable`
  走统一 fallback；**不**登记为缺凭据（`_skipped` 不含该键）。
- 结果：数据源进入 0；返回 `DATA_UNAVAILABLE`；`acquire` 仍返回非 `skipped`。

**问题 2：`_attach_skip_state` 修改调用者 config，复用同一 config 两次运行共享 state。**
- 复现：`test_same_config_two_stream_runs_are_independent`（先行失败：调用者 config 被写入 `fr_skip_state`）。
- 修复（`trading_graph.py`）：
  - `_attach_skip_state` 不再原地修改：复制 `config`/`configurable` 后返回**新 args**；`reuse=False`
    时强制新建状态，`reuse=True` 时保留已有状态（供 debug 复用）。
  - `_run_graph`（propagate/debug）：`reuse=False`，每次新状态。
  - `stream_run`（直接 CLI）：对副本附加；debug 传入的 args 已含状态 → 复用，不重置。
- 结果：同一 config 连续两次 `stream_run`，运行 1 缺 key（1 条跳过、进入 1），运行 2 恢复模拟 key
  正常调用（无跳过日志）；调用者原始 config **未被修改**（无 `fr_skip_state`，与快照一致）。
- debug 路径仍只记录一次跳过日志（`test_debug_multi_macro_requests_skip_once` 通过）。

### 验收覆盖（实现后全部通过）

- 缺 key：工具请求 N、数据源进入 1、HTTP 0、跳过日志 1、N 个哨兵。
- 空串/空格/纯空白：`get_api_key` 与真实 `get_macro_data`（仅替换网络出口并计数）均未配置、
  零 HTTP；对照组有 key 时确达网络出口。
- 多请求（同轮并发 3 个 macro）三路径：`propagate` / `debug` / 直接 `stream_run` —
  工具请求 >1、数据源进入 1、HTTP 0、日志 1、整图完成。
- 真实并发：外层 Barrier + 桩内 Event 门控、主线程放行；winner-only 进入。
- **等待超时**：等待者不进入数据源、不登记跳过、走明确诊断 + fallback。
- 独立 Context 共享对象：日志 1。
- 两次运行隔离：各 1 条日志（合计 2）。
- **同一 config 复用两次运行**：互不影响，调用者 config 不被修改。
- 同实例并发两跑（多请求）：各进入 1（合计 2）、日志 2、无线程残留、worker 异常全捕获。
- 流式配置隔离：调用者 English、图 French；图内 French，两次 `next` 之间与结束后 English。
- fallback：`fred,backup` → FRED 跳过 1 条日志，续用 backup 数据。
- 网络异常不登记跳过（再次调用仍进入）。
- 配置恢复：缺 key 运行 1 条日志；下一次有 key 正常运行、无跳过日志。

---

## 3. 未解决问题 / 备注

- 无已知功能缺陷。全部新增与现有离线测试通过，lint 通过。
- `langgraph_aws` 可选依赖缺失导致 bedrock 测试跳过，属环境、非本次问题。
- 本阶段**未**提交、推送或合并。
- 说明：`vendor_skip.RunSkipState` 默认 `wait` 超时 30s；等待超时现在走明确诊断 + fallback，
  **不**调用该 vendor、**不**登记为缺凭据（本轮修复）。

## 4. 相关文件

- 新增：`tradingagents/dataflows/vendor_skip.py`
- 修改：`tradingagents/dataflows/vendors/fred.py`、`tradingagents/dataflows/router.py`、
  `tradingagents/agents/tools.py`、`tradingagents/graph/trading_graph.py`
- 测试：`tests/test_fr_c2_acceptance.py`、`tests/test_fr_c2_paths.py`（含本轮两条回归：
  等待超时不进入数据源；同一 config 两次运行独立且不污染调用者）、`tests/test_fr_c2_probe.py`（前置探针）
