# FR-C2 验收测试（test-first）设计与实际结果

- 日期：2026-11-17
- 阶段：**测试先行（test-first）**，只新增/补强测试，**未修改生产代码**
- 依据：已批准的 `docs/req/fr-c2-plan.md`
- 数据/模型：全部模拟；不读取真实凭据，不联网
- 说明：跳过功能尚未实现，因此失败是**预期的“功能未实现”**；未跳过、未弱化任何测试。

## 运行环境（实际依赖版本）

| 包 | 版本 |
|---|---|
| Python | 3.14.4 |
| langgraph | 1.2.22 |
| langgraph-checkpoint-sqlite | 3.1.3 |
| langchain-core | 1.8.1 |
| pandas | 3.1.1 |
| pytest | 9.2.0 |
| tradingagents（本仓库） | 0.7.1 |

命令（仓库根目录，临时 venv）：

```bash
/tmp/opencode/fr-c2-venv/bin/python -m pytest tests/test_fr_c2_acceptance.py tests/test_fr_c2_paths.py -q
/tmp/opencode/fr-c2-venv/bin/ruff check tests/test_fr_c2_acceptance.py tests/test_fr_c2_paths.py
```

## 新增/补强的测试

- `tests/test_fr_c2_acceptance.py`：router 层与 `RunSkipState` 契约（计数、去重、并发、隔离、fallback、配置恢复、真实 FRED 函数空白 key 路径）。
- `tests/test_fr_c2_paths.py`：三个运行入口（`propagate` / `debug` / 直接 `stream_run`）的多请求与配置隔离，以及同实例并发隔离。

### 本轮补强要点（对应审核意见）

1. **多请求路径**：新增 `MacroHeavyModel`，在一次分析的首轮**同一轮并发**发出 3 个
   `get_macro_indicators`（不同指标），另加其他工具各一次。`propagate` / `debug` / 直接
   `stream_run` 三条路径都断言：**工具请求数 > 1**、数据源进入 **1**、HTTP **0**、跳过日志 **1**、整图完成。
2. **真实 FRED 函数路径**：新增 `test_real_get_macro_data_blank_key_makes_no_http[...]`
   （空串/空格/纯空白），调用**真实的** `fred.get_macro_data`，仅替换网络出口
   `tradingagents.dataflows.net.requests.get` 并计数；断言未配置时 `FredNotConfiguredError`
   且 HTTP 计数为 0。另加 `test_real_get_macro_data_with_key_counts_http` 作**对照**：有(假)key
   时真实路径确实到达（被 patch 的）网络出口，证明计数器接的是真实函数，空白 key 的“零 HTTP”不是假函数造成的假象。
   - 保留原有“计数桩”测试（`_fred_entry_counter`）用于测数据源进入次数。
3. **流式配置隔离**：`test_direct_stream_run_config_isolation_english_caller_french_graph`：
   调用者配置 English，图配置 French；断言图内工具看到 French，两次 `next` 之间及结束后
   调用者仍为 English。
4. **并发健壮性**：所有并发测试在 worker 内 `try/except BaseException` 收集异常（加锁），
   主线程在 `finally` 中 `release.set()` 并 `join` 全部线程；断言**无线程存活**后再断言计数，
   即使断言失败也先释放 Event、回收线程。`Barrier` 带 `timeout`。

### 测试写法（如实暴露失败，不弱化）

- `tradingagents.dataflows.vendor_skip.RunSkipState` 在**每个测试内部**导入，而非模块级
  `importorskip`。收集正常，每个用例如实失败于 `ModuleNotFoundError`（功能未实现）。
  刻意**不**用 `pytest.importorskip`，否则整文件“跳过”会掩盖缺失功能。
- 不联网：`test_system_isolation` 的 autouse fixture 已禁 socket；本文件另在网络出口处
  patch 并计数/抛错，双重保证。
- 计数区分：`_tool_request_counter` 计“工具请求到达 vendor 的次数”，`_fred_entry_counter` /
  内联桩计“数据源函数进入次数”，`_count_macro_http` 计“HTTP 出口次数”，`caplog` 计“跳过日志”。
  三者互不混用。

## 覆盖矩阵与预期

| 用例 | 覆盖点 | 预期（实现后） |
|---|---|---|
| `test_missing_key_one_log_no_http_sentinel_per_call` | 缺 key N=5 | 进入 1、HTTP 0、日志 1、5 哨兵 |
| `test_blank_key_is_unconfigured[empty/spaces/whitespace]` | 真实 `get_api_key` | 均抛 `FredNotConfiguredError` |
| `test_real_get_macro_data_blank_key_makes_no_http[...]` | 真实 `get_macro_data`，仅替换网络 | 抛错且 HTTP 0 |
| `test_real_get_macro_data_with_key_counts_http` | 对照组 | 有 key 时到达网络出口（HTTP ≥ 1） |
| `test_repeated_calls_across_indicators_enter_source_once` | 3 指标×3 | 进入 1、日志 1 |
| `test_concurrent_first_entry_enters_winner_only` | 6 线程真实并发 | 进入 1、日志 1、无死锁 |
| `test_same_state_under_copied_contexts_logs_once` | 独立 Context 共享对象 | 进入 1、日志 1 |
| `test_two_runs_isolated_one_log_each` | 两独立 state 并发 | 各进入 1（共 2）、日志 2 |
| `test_fred_skip_continues_to_next_fallback_vendor` | `fred,backup` | 返回 backup、日志 1 |
| `test_network_error_is_not_marked_as_skip` | `VendorUnavailableError` | 不登记跳过（再进 2 次） |
| `test_next_run_with_key_fetches_normally` | 缺key→有key | 运行1日志1；运行2正常无跳过 |
| `test_propagate_multi_macro_requests_skip_once` | 普通，多次 macro | 请求>1、进入1、HTTP0、日志1、完成 |
| `test_debug_multi_macro_requests_skip_once` | debug，多次 macro | 同上（内层不重置） |
| `test_direct_stream_run_multi_macro_requests_skip_once` | 直接 stream_run，多次 macro | 同上 |
| `test_direct_stream_run_config_isolation_english_caller_french_graph` | 调用者 English/图 French | 图内 French；之间/结束后 English；计数同左 |
| `test_same_graph_instance_concurrent_runs_are_isolated` | 同实例并发两跑，多次 macro | 各进入1（共2）、日志2、无线程残留 |

## 实际结果（本阶段，未实现功能）

```
17 failed, 3 passed in ~3s
```

（本轮补强前为 `14 failed, 1 passed`；补强后新增若干用例与两组参数化，故总数变化。）

**通过（3）及原因——均为当前代码已恰好满足的独立点，不代表验收完成：**

- `test_blank_key_is_unconfigured[empty]`：当前 `get_api_key` 用 `if not api_key`，空串已算未配置。
- `test_real_get_macro_data_blank_key_makes_no_http[empty]`：同上，空串在 HTTP 前抛错。
- `test_real_get_macro_data_with_key_counts_http`：对照组，fake 网络响应可用（已修 `raise_for_status`），真实函数到达网络出口。

**失败（17）——全部为“功能未实现”，已逐条核对，无测试自身错误、无环境问题：**

| 失败原因 | 用例数 | 说明 |
|---|---|---|
| `ModuleNotFoundError: tradingagents.dataflows.vendor_skip` | 8 | `RunSkipState` 未实现（方案 §5/§9） |
| `DID NOT RAISE FredNotConfiguredError`（空格/纯空白） | 2 | `get_api_key` 未 `strip()`（方案 §7） |
| `network must not be reached with a blank key`（真实函数，空格/空白） | 2 | 同上：空白 key 未挡在 HTTP 前（方案 §7） |
| `data source entered 3 times, expected 1`（多请求路径×3） | 3 | FRED 未跳过、未记忆，进入 3 次（方案 §5/§7） |
| `assert 'French' == 'English'`→已修为 `assert 3 == 1` | 1 | 配置隔离断言已通过；剩余为数据源进入 3 次未跳过 |
| `each run enters FRED once; got 6` | 1 | 同实例并发两跑、每次多请求（3×2=6），未去重/未隔离 |

说明：`test_direct_stream_run_config_isolation...` 的**配置隔离部分已通过**（图内 French、之间/结束后 English），
其失败仅剩数据源进入计数（当前 3，期望 1），即功能未实现；这不是测试自身错误。

逐行摘要（`--tb=line`，节选）：

```
tests/test_fr_c2_acceptance.py:47   ModuleNotFoundError: No module named 'tradingagents.dataflows.vendor_skip'  (x8)
tests/test_fr_c2_acceptance.py:123  Failed: DID NOT RAISE FredNotConfiguredError                               (x2)
tests/test_fr_c2_acceptance.py:141  AssertionError: network must not be reached with a blank key              (x2)
tests/test_fr_c2_paths.py:178       AssertionError: data source entered 3 times, expected 1                    (x1)
tests/test_fr_c2_paths.py:201       AssertionError: debug path entered FRED 3 times (must not reset)          (x1)
tests/test_fr_c2_paths.py:225       AssertionError: stream_run entered FRED 3 times                           (x1)
tests/test_fr_c2_paths.py:276       assert 3 == 1                                                             (x1)
tests/test_fr_c2_paths.py:335       AssertionError: each run enters FRED once; got 6                           (x1)
```

## 已修复的测试自身错误（记录，避免混淆）

本轮初跑暴露并**已修正**的测试缺陷（与功能无关）：

1. `MacroHeavyModel` 误用 `self._text()`（不存在）→ 改用模块级 `TEXT`。
2. 对照组 fake 响应缺 `raise_for_status` → 补齐。
3. 配置隔离测试原先把“构造 graph 即 `set_config(graph_config)`”误当泄漏 → 改为**构造 graph 之后**
   再 `set_config({"output_language": "English"})`，从而正确建模“调用者 English / 图 French”。
4. 并发测试改为在 `finally` 释放 Event、`join` 全部线程并断言无线程存活；worker 异常加锁收集。

## Lint

```bash
/tmp/opencode/fr-c2-venv/bin/ruff check tests/test_fr_c2_acceptance.py tests/test_fr_c2_paths.py
# All checks passed!
```

## 结论

- 已按审核意见补强：多请求（含同轮并发）三路径、真实 FRED 函数空白 key 零 HTTP 路径与对照组、
  流式 English/French 配置隔离、并发异常捕获与 finally 清理。
- 当前 `17 failed, 3 passed`。失败**全部**归因于功能尚未实现（缺 `vendor_skip`、空白 key 未
  `strip()`、未跳过/未去重/未隔离）；**没有**测试自身错误或环境问题（本轮曾有的测试缺陷已修复并记录）。
- **缺失模块导致的失败仅记录为“尚未实现”，不能据此断言“后续不存在测试自身错误”**；后续实现后
  仍需重新运行并逐一核对每个失败的真实原因。
- 未跳过、未弱化任何测试。按约定停在此处，等待审核后再进入实现。
