# FR-C2 方案与实现说明（最终版，已实现并审核通过）

## 目标

未配置或无凭据的数据源必须跳过并记录，不得在同一次运行中重试。

验收标准：缺少 `FRED_API_KEY` 时零重试，每次分析运行只记录一条跳过日志，整体继续运行。

> 状态：已实现并审核通过（含两轮审核修复）。本文件已更新为**最终实际行为**；
> 实际代码/测试结果见 `docs/evidence/fr-c2/implementation-verification.md`，
> 前置技术验证见 `docs/evidence/fr-c2/configurable-probe.md`，
> 测试先行记录见 `docs/evidence/fr-c2/test-first.md`。

## 修订历史（真实记录）

1. **初稿**：提出 ContextVar[frozenset] + GIL 的并发去重方案。
2. **第一次修订**：放弃可变 ContextVar 去重；改为“每次运行独立的共享状态对象 + 锁保护
   check-and-add”，并明确 configurable 传播、生命周期、单一日志层。
3. **第二次修订**：把“查跳过 + 查在途资格 + 装 Event”合并为锁内原子 `acquire`；
   `finish` 置于 `finally`；等待者走统一异常/fallback；`configurable` 不进 checkpoint
   改为“待实测假设”，先做前置探针。
4. **探针验证**：验证 configurable 对象可达真实工具、checkpoint 写入/读取、异常时仍写入、
   真实中断恢复用新对象、且不被持久化（见 `configurable-probe.md`）。
5. **测试先行**：先写验收测试（如实暴露“功能未实现”失败，见 `test-first.md`）。
6. **实现**：新增 `RunSkipState`；router 角色化跳过；单一日志；跳过后继续 fallback；
   三入口传局部状态（见 `implementation-verification.md`）。
7. **审核修复 1**：等待超时（`wait` 返回 None）不得进入数据源，改走明确诊断 + fallback，
   且不登记为缺凭据。
8. **审核修复 2**：`_attach_skip_state` 不再原地修改调用者 config；复制 config/configurable，
   每次独立运行新建状态，仅 debug 内部调用复用当前运行状态。

分析仅针对当前项目，独立完成，不参考其他分支，且未读取任何真实凭据（`.env`、`auth.json` 等）。

---

## 1. 当前调用路径

| 层 | 位置 | 说明 |
|---|---|---|
| Agent 提示词/工具绑定 | `tradingagents/agents/analysts/news_analyst.py:13-18`、`:56` | news analyst 绑定 `get_macro_indicators`，由 LLM 在多轮 tool call 中反复调用 |
| 工具定义 | `tradingagents/agents/tools.py:232-264` | `@tool get_macro_indicators(...)`，`:264` 调 `route_to_vendor("get_macro_indicators", ...)`；已用 `InjectedState` 从图 state 取 `trade_date` |
| 路由器 | `tradingagents/dataflows/router.py:200-297` | `route_to_vendor` 取 vendor 链，`:231-259` 循环调用实现 |
| vendor 映射 | `router.py:142-144`、`:20` | `get_macro_indicators -> {"fred": get_macro_data}` |
| 未配置分支（vendor 链内） | `router.py:243-247` | 捕获 `VendorNotConfiguredError`：**每次调用**都 `logger.warning(...)`（`:244`）并 `continue` |
| 未配置分支（兜底） | `router.py:288-294` | 链走完后可选类别返回 `DATA_UNAVAILABLE...`，**每次调用**再一条 warning（`:290`） |
| FRED 数据函数 | `tradingagents/dataflows/vendors/fred.py:167-286` | `get_macro_data` |
| 配置检查 | `fred.py:102-110` | `get_api_key()` 读 `os.getenv("FRED_API_KEY")`，缺失抛 `FredNotConfiguredError`（`:93-99`，继承自 `VendorNotConfiguredError`→`errors.py:53`） |
| HTTP | `fred.py:146-164` (`_request`) → `net.py:6-24` (`get_scrubbed`) | 仅 `get_api_key()` 之后才会走到 HTTP |
| 图的 state | `tradingagents/agents/state.py:45`、`graph/propagation.py:13-65` | `AgentState`（`MessagesState` + 字段）；初始 state 由 `create_initial_state` 构造 |
| checkpoint | `tradingagents/graph/checkpointer.py:28-43` | SqliteSaver 只序列化**图 state 与 writes**，不序列化 `RunnableConfig.configurable` |
| 运行作用域（先例） | `tradingagents/graph/trading_graph.py:185`、`dataflows/config.py:13,44-62` | 已有 `run_config` / `ContextVar` / `run_config_context` 作为“一次运行”边界的先例 |

---

## 2. 当前行为核对

- 缺 key 时**唯一**的 HTTP 触发点在 `fred.py:214` 的首次 `_request`，而 `get_api_key()` 在此之前抛错，所以 HTTP = 0。
- 每次 `get_macro_indicators`（`tools.py:264`）→ 每次 `route_to_vendor`（`router.py:200`）→ 每次 `get_macro_data`（`fred.py:167`）。整链无缓存、无重试。
- 缺 key 当前每次调用产生 **2 条 WARNING**：`router.py:244` + `router.py:290`。**两处都要处理**。
- 运行边界现状：`propagate` 用 `with run_config(...)`（`trading_graph.py:185`）；`debug` 分支在 `propagate` 内（`:386-396`）内部调 `stream_run`；CLI 直接 `stream_run`（`cli/run.py:241`）；`stream_run` 用 `run_config_context`（`:422`），调用者与图在**同一线程**交替推进。

---

## 3. “零重试”的精确定义

**零重试** = 对“凭据缺失”这一确定性不可用原因，一次运行内**只对数据源函数进入一次**，其后不再进入数据源函数、不再发 HTTP、不再重复产生跳过日志。

它**不**表示调用方拿到异常——每次工具请求仍返回 `DATA_UNAVAILABLE` 哨兵（供模型看到），但跳过日志一次运行仅一条。

**已决定：router 层跳过。** 已确认缺凭据的 vendor，在同一次运行的后续调用中由 router 直接判定，**不进入数据源函数**。

---

## 4. 预期计数（缺 `FRED_API_KEY`，`macro_data=fred`，一次运行）

设 N = 该次运行的 macro 工具请求次数（N ≥ 1）。

| 计数对象 | 当前 | 修订后 | 说明 |
|---|---|---|---|
| 工具请求 `get_macro_indicators` | N | **N**（不变，由 LLM 决定） | |
| router `route_to_vendor` 调用 | N | **N**（不变） | |
| 数据源函数 `get_macro_data` **进入次数** | N | **1** | 由“首次进入协调”保证恰好一次（见 §5） |
| HTTP `requests.get` | 0 | **0** | 检查在数据源函数内、任何 HTTP 之前 |
| 跳过日志（累计） | 2N | **1**（每次运行） | 单一层负责记录（见 §7） |
| 其余故障日志（HTTP 400/网络/坏 indicator 等） | 每次 | **每次**（不变） | 只去重“缺凭据” |
| 返回给 agent 的哨兵 | N | **N** | 抑制的是日志与重复数据源访问，不是工具返回值 |

因已决定“跳过 FRED 后**继续遍历 fallback** 而不是直接返回哨兵”，若将来 FRED 链有其他 vendor，后续 vendor 仍会被尝试（见 §6）。

---

## 5. 运行状态对象 + 首次进入协调（核心修订）

**状态只保存安全原因码，不保存异常或凭据**；`RunSkipState` 每次运行新建，作为**局部对象**沿调用链传递，**不存入 `self`**。

采用**单一原子协调原语**：不是“先 `is_skipped` 再 `claim_first`”，而是把“查跳过 / 查是否已有资格 / 安装 Event / 返回资格”放在**同一把锁内**完成，取得资格后**无需也不允许**再单独 `is_skipped`（把两个动作合并为原子操作，消除“登记释放后再次拿到首次资格”的竞态）。

新增 `tradingagents/dataflows/vendor_skip.py`：

```python
import threading

class RunSkipState:
    """One run's skip bookkeeping. Safe to share across tool worker threads."""
    def __init__(self):
        self._lock = threading.Lock()
        self._coord = {}        # vendor_key -> _Slot（在途的首次检查）
        self._skipped = set()   # vendor_key 已确认缺凭据（只存原因码，不存异常）

    def acquire(self, vendor_key):
        """Atomically decide this caller's role for vendor_key.

        Returns one of:
          ("skipped", None)          -> already known missing credentials
          ("winner", slot)           -> THIS caller runs the config check
          ("waiter", slot)           -> another caller is checking; wait on slot.event
        All decisions are made under the lock, so the skip state and the
        in-flight slot cannot change between deciding and acting.
        """
        with self._lock:
            if vendor_key in self._skipped:
                return ("skipped", None)
            slot = self._coord.get(vendor_key)
            if slot is None:
                slot = _Slot(threading.Event())
                self._coord[vendor_key] = slot
                return ("winner", slot)
            return ("waiter", slot)

    def finish(self, vendor_key, slot, skipped):
        """End the winner's turn: publish the outcome and wake waiters.

        ALWAYS called in a finally block, so waiters are never stranded even
        when the winner returns or raises. Returns True only if this is the FIRST
        time vendor_key is recorded skipped, so the caller emits exactly ONE skip
        notice per run. If skipped, the reason code stays in _skipped so later
        acquire() calls answer ("skipped", None) directly.
        """
        newly_skipped = False
        with self._lock:
            slot.skipped = skipped
            if skipped and vendor_key not in self._skipped:
                self._skipped.add(vendor_key)
                newly_skipped = True
            if self._coord.get(vendor_key) is slot:
                del self._coord[vendor_key]
        slot.event.set()   # set outside the lock; Event.set is idempotent
        return newly_skipped
```

`_Slot` 只是一个持有 `event` 与不可变结果位的小结构；结果位在 `finish` 内、删除 `_coord` 条目之前写入，交给等待者在唤醒后读取。

### 并发首次进入的协调（不依赖执行顺序）

- **原子决策**：`acquire` 在**同一把锁内**同时判定“是否已跳过”和“是否装 Event”。因此不存在“`is_skipped` 通过 → 别人登记并释放 → 我又拿到首次资格”的时间窗：一旦 `_skipped` 含该键，`acquire` 直接返回 `skipped`；若在途槽存在，返回 `waiter` 并绑定**同一** slot；只有真正第一人才是 `winner`。
- **资格与跳过合二为一**：`winner` 取得资格即代表“此刻未被判定跳过”，因此不需要、也不允许在取得资格后再 `is_skipped`（那正是竞态来源）。`waiter` 被唤醒后读取 `slot.skipped` 的**不可变结果**，不再重新 `acquire`（避免同一次等待后又被别人释放、再次获得首次资格）。
- **释放必须在 `finally`**：`winner` 的 `try/finally` 中**无论成功 `return`、正常结束还是抛异常**都调用 `finish(...)`。成功路径**不靠 `else`**（`try` 里的 `return` 不会执行 `else`），而是把 `skipped=False` 在 `finally` 里提交，保证等待者一定被唤醒。
- **等待者**：`slot.event.wait(timeout)`，**超时视同失败**。被唤醒后若 `slot.skipped` 为“已跳过”则进入**统一跳过流程**（`continue` 到下一个 vendor）；若为“未跳过（有 key，winner 已成功）”则**重新走同一套调用与统一异常处理**；若**等待超时**（返回 `None`）：**不**调用该 vendor，记录明确诊断并以 `VendorUnavailableError` 走统一 fallback，**不**登记为缺凭据（见 §7）。
- **日志**：仅 `winner` 且 `finish(skipped=True)` **返回 True（首次登记）** 时记录那条唯一跳过日志；等待者/后续调用不记录。日志放在锁外（避免持锁 I/O）。
- **有 key 的正常情形**：`winner` 成功，`finish(skipped=False)` 唤醒等待者；等待者按统一路径正常进入数据源（多次进入是有 key 的正常行为，不属于本验收）。

这个机制**不依赖执行顺序**：所有线程经同一把锁决定角色，无论同时到达还是先后到达，恰好一个 `winner`，其余要么直接 `skipped`、要么等 `waiter` 的不可变结果。

---

## 6. 状态传播：明确选 `configurable`，并核对 checkpoint 序列化

**选型**：使用 LangGraph 的 `RunnableConfig.configurable` 传递 `RunSkipState` 引用（不传值、不序列化）。

- **已验证**：前置探针（`docs/evidence/fr-c2/configurable-probe.md`）确认 `SqliteSaver` 只序列化图
  state 与 writes，`configurable` 里的 `RunSkipState`（含 `Lock`/`Event`）**不进入 checkpoint**，
  checkpoint 写入/读取/中断恢复均正常，恢复时用调用方传入的新对象。

**具体接入位置（graph → tools.py → router）**：

1. `tradingagents/graph/trading_graph.py`：
   - `_new_skip_state()` / `_attach_skip_state(args, state=None, reuse=...)`：**复制**
     `config`/`configurable` 后返回新 `args`，**不修改调用者字典**；`reuse=False` 时强制新建，
     `reuse=True` 时保留已有状态（供 debug 复用）。
   - `_run_graph`（`propagate` 与 `debug` 共用）：`reuse=False`，每次新状态。
   - `stream_run`（CLI 直接路径）：对副本附加（`reuse=True`）；debug 传入的 args 已含状态 → 复用，
     不重置，故 debug 仍只记一条跳过日志。
2. `tradingagents/agents/tools.py`：
   - `get_macro_indicators` 增加 `config: RunnableConfig` 注入参数，从
     `config["configurable"]["fr_skip_state"]` 取出 `RunSkipState` 并传给
     `route_to_vendor("get_macro_indicators", ..., state=state)`；取不到时传 `None`。
3. `tradingagents/dataflows/router.py`：`route_to_vendor(method, *args, state=None, **kwargs)`；
   缺省 `None` 时惰性建 `RunSkipState()`（仅本次调用生命周期）。

---

## 7. 跳过 → 继续 fallback（不直接返回哨兵）+ 单一日志层 + 统一异常路径

`route_to_vendor` 的 vendor 循环（`router.py:231-259`）改为**角色化**流程。核心要求：**无论 winner 还是 waiter，成功进入数据源后都经过原有统一 `try/except`**；等待者**不**另写裸 `return impl_func(...)`；`finish(...)` 一律在 `finally`：

```
for vendor in vendor_chain:
    key = f"{vendor}:not_configured"
    slot = None
    skipped = False
    try:
        role, slot = state.acquire(key)          # 锁内原子：skipped / winner / waiter
        if role == "skipped":
            continue                              # 已确认缺凭据：不进数据源，继续 fallback
        if role == "waiter":
            decided = state.wait(slot)
            if decided is True:
                continue                          # winner 判定跳过，继续下一个 vendor
            if decided is None:
                # 超时：不调用该 vendor，明确诊断 + fallback，不登记跳过
                last_unavailable = VendorUnavailableError("did not confirm in time")
                continue
            # decided is False（有 key）：落入下面的统一调用
        # —— 统一调用与统一异常处理（winner 与 waiter 共用同一段）——
        try:
            return impl_func(*args, **kwargs)
        except VendorNotConfiguredError:
            skipped = True                        # 仅凭据缺失登记为跳过
            ...                                   # 记 first_error / continue 等原逻辑
            continue
        except VendorUnavailableError as e:
            last_unavailable = e                  # 网络/限流：绝不登记为跳过
            continue
        except Exception as e:
            failed = e                            # 其他错误：原诊断日志，继续 fallback
            continue
    finally:
        # winner 发布结果并唤醒等待者；仅首次跳过时写唯一一条日志
        if role == "winner" and state.finish(key, slot, skipped=skipped):
            logger.warning("... skipping it for this run ...")
```

（上述为示意；实际按现有 `router.py` 的 `last_no_data / last_unavailable / failed / first_error / skip_seen` 变量组织，保持原有哨兵与优先级。）

- **统一异常与 fallback**：waiter 被唤醒若“有 key 未跳过”，进入**同一个** `try: return impl_func(...)` 与同一组 `except`，不在等待分支裸调用。**等待超时**：不调用该 vendor，记 `VendorUnavailableError` 走统一 fallback，并在日志给出明确诊断，**不**登记跳过。
- **网络异常不得登记为缺凭据**：只有 `VendorNotConfiguredError` 置 `skipped=True`；`VendorUnavailableError`（网络/限流）、`NoMarketDataError`、其他异常一律 `skipped=False`，保留原有诊断与 fallback 行为。
- **跳过 FRED 后继续遍历 fallback**：用 `continue`，不 `return` 哨兵。
- **单一日志层**：跳过日志只在 router 一处写，且仅当 `finish(skipped=True)` 返回 True（首次登记）时写一条（FRED 的 `get_api_key` **不**记跳过日志，只抛 `FredNotConfiguredError`）。
- **兜底 warning（`router.py:288-294`）**：只对**非缺凭据**的 `first_error` 写；缺凭据场景已由上面的单条日志记录一次，兜底分支**不再**为同一原因重复 warning。若链上所有 vendor 都因缺凭据被跳过，最终仍返回该类别的现有哨兵（可选类别）或抛首个非跳过错误（核心类别，保持现状）。
- **空字符串 / 纯空白 key**：`fred.get_api_key` 改为 `api_key = (os.getenv("FRED_API_KEY") or "").strip()`，为空即未配置（你已确认）。

---

## 8. 生命周期：三个入口，状态为局部对象

- `propagate`：`_run_graph` 以 `reuse=False` 新建 `RunSkipState` 并附加到**副本** config；`debug` 分支
  复用同一对象（不重置）。
- `debug`：在 `propagate` 内部，经 `_attach_skip_state(reuse=True)` 复用当前运行状态，**不重复重置**，
  仍只记一条跳过日志。
- 直接 `stream_run`（CLI）：对传入 args 的**副本**附加状态（`reuse=True`；debug 传入已含状态则复用）；
  **不修改调用者字典**。复用同一份 config 连续两次 `stream_run`，每次得到独立的运行状态；用完即弃，
  **无跨 yield 的全局 set**，不污染调用者。
- **不存 `self._skip_state`**：所有入口都用局部变量。故同一个 `TradingAgentsGraph` 实例并发跑两次分析时，各自持有不同的 `RunSkipState`，互不干扰。
- **异常退出**：局部对象随调用栈释放；`winner` 的 `finish(...)` 在 `finally` 中执行（成功 `return`、`continue`、抛异常都会释放等待者）。等待者 `wait(timeout)` 有超时，绝不永久阻塞；超时走诊断 + fallback，不登记跳过。
- **下一次运行重新检查配置**：`get_api_key()` 每次读 env；新运行新对象；不缓存 key 或“缺配置”结论。
- **fallback 顺序不变**：只改“是否进入数据源 / 是否写日志”，vendor 链与优先级不变。

---

## 9. 最终修改清单（已落地）

1. 新增 `tradingagents/dataflows/vendor_skip.py`：`RunSkipState`（`threading.Lock` 保护 `acquire`/`finish`
   的原子决策；`threading.Event` 协调首次进入；`finish` 在 `finally` 调用并返回“是否首次跳过”；
   只存原因码）。
2. `tradingagents/dataflows/vendors/fred.py`：空串/纯空白视为未配置（`.strip()`）；**不**写跳过日志
   （日志统一由 router 负责）。
3. `tradingagents/dataflows/router.py`：签名加 `state=None`；循环角色化（`acquire` → winner/waiter/skipped；
   统一 `try/except`；`finally: finish(...)`；**等待超时不调用 vendor**）；兜底 warning 仅对非缺凭据写。
4. `tradingagents/agents/tools.py`：`get_macro_indicators` 增加 `config: RunnableConfig` 注入，取
   `configurable["fr_skip_state"]` 传给 `route_to_vendor(..., state=...)`。
5. `tradingagents/graph/trading_graph.py`：`_new_skip_state`/`_attach_skip_state`（**复制 config，不改调用者**）；
   `_run_graph` 每次新状态；`stream_run` 对副本附加、debug 复用。
6. 不改 `get_macro_data` 的 HTTP/解析逻辑，不引入重试，不改 fallback 顺序。

---

## 10. 测试记录（已实现并运行）

前置 configurable/checkpoint 探针已通过，见 `docs/evidence/fr-c2/configurable-probe.md`。
验收测试先行记录见 `docs/evidence/fr-c2/test-first.md`；最终实施与结果见
`docs/evidence/fr-c2/implementation-verification.md`。

实际测试文件：

- `tests/test_fr_c2_acceptance.py`：缺 key 计数、空/空格/空白 key（含真实 `get_macro_data` 仅换网络出口）、
  重复调用、真实并发（外层 Barrier + Event 门控）、独立 Context、两次运行隔离、fallback、网络异常不登记、
  配置恢复、**等待超时不进入数据源**。
- `tests/test_fr_c2_paths.py`：`propagate`/`debug`/直接 `stream_run` 多请求（>1、进入1、HTTP0、日志1、完成）、
  流式 English/French 配置隔离、同实例并发隔离、**同一 config 两次运行独立且不污染调用者**。
- `tests/test_fr_c2_probe.py`：前置探针（对象传递、checkpoint 持久化、异常仍写、真实中断恢复用新对象）。

执行与结果（详见 `implementation-verification.md`）：

1. 针对性：`pytest tests/test_fr_c2_acceptance.py tests/test_fr_c2_paths.py tests/test_fr_c2_probe.py tests/test_fred.py tests/test_vendor_routing.py tests/test_vendor_errors.py tests/test_graph_end_to_end.py tests/test_checkpoint_lifecycle.py -q`
2. 完整离线回归：`pytest -q`（默认 `-m "not integration"`，conftest 已禁网）。
3. Lint：`ruff check <改动文件与测试>`。

约束：所有测试 mock 网络出口、使用脚本化 `BaseChatModel`；**不读取真实凭据、不使用真实付费模型**。

---

## 11. 已确认决定（记录）

1. router 层跳过同次运行中已确认缺凭据的 FRED，不重复进入数据源函数。
2. `FRED_API_KEY` 为空字符串或纯空白均视为未配置。
3. 允许修改 `router.py` 与 `trading_graph.py`，覆盖普通 `propagate`、`debug`、直接 `stream_run`。
4. 状态为每次运行的局部对象，不存入 `self`。
5. 跳过 FRED 后继续遍历 fallback，不直接返回哨兵。
6. 状态只保存安全原因码；不保存原始异常或凭据。
7. 跳过日志由单一层（router）负责，FRED 与 router 不重复记录。
8. 首次进入的 `acquire` 把“查跳过 + 查在途资格 + 装 Event”合并为**锁内原子操作**；取得资格后不再单独 `is_skipped`。
9. `finish(...)` 一律在 `finally` 调用，成功 `return` 路径也保证唤醒等待者。
10. 等待者被唤醒后走**统一 `try/except` 与 fallback**，不裸调用数据源；网络等其他异常不登记为跳过。
11. 并发测试只用**外层 Barrier** 制造竞争；数据源桩内用 `Event` 暂停、由测试主线程放行，且都带超时。
12. `configurable` 不进 checkpoint 已由前置探针实测通过（写入/读取/中断恢复均正常，且不被持久化）。
13. **（审核修复）等待超时**：waiter 的 `wait` 返回 `None` 时**不**调用该 vendor，记录明确诊断并以
    `VendorUnavailableError` 走 fallback，**不**登记为缺凭据。
14. **（审核修复）config 不被污染**：`_attach_skip_state` 复制 config/configurable 后返回新 args；
    每次独立运行新建状态，仅 debug 内部调用复用当前运行状态。复用同一 config 连续两次运行互相独立。
15. 跳过日志只在 router 一处、且仅当首次登记跳过时写一条（`finish` 返回 True）。
