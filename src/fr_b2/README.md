# FR-B2 — 报告结论引用检查（Citation Traceability Checker）

检查待查清单中列出的结论及其引用，定位报告原文和已登记证据的原文行。引用缺失、
格式错误、来源编号不存在、证据文件缺失，或引用位置在证据中找不到原文时，该结论标为
`UNTRACEABLE`，并从 `supported` 统计中剔除。每条记录使用一个 `citation` 对象，
该引用通过全部定位检查后标为 `SUPPORTED`。

- 入口：`fr_b2/check_citations.py`（`python -m fr_b2.check_citations`）
- 只依赖 Python 标准库，**离线**运行，不调用模型、不联网、不 import TradingAgents 内部模块。
- 对应需求：`docs/req/requirements-options.yaml` 中的 `FR-B2`（Owner B：结论可信）。

## 1. 判定结果

| 状态 | 含义 |
|---|---|
| `SUPPORTED` | 该记录的引用解析到证据原文；计入 `supported` |
| `UNTRACEABLE` | 任一检查失败；**不计入** `supported` |

失败原因码（`reason`）：

| reason | 触发条件 |
|---|---|
| `claim_not_found` | `report_span` 缺失/非法，或只给行号没有原文片段，或片段不在该行 |
| `missing_citation` | 结论没有引用 |
| `malformed_citation` | 引用字段缺失或类型错误（如 `source_line` 非整数、`source_id` 为空） |
| `unknown_source` | `source_id` 不在来源表 |
| `missing_evidence` | 来源登记的证据文件不存在 |
| `unreadable_evidence` | 证据文件存在但无法按 UTF-8 读取（只影响该条） |
| `invalid_locator` | 引用的行号越界，或该行不含 `expected_snippet` |

汇总字段：`total`、`supported`、`untraceable`；`supported` 仅统计 `SUPPORTED`。

## 2. 输入文件格式

### 来源表（`--sources`）
```json
{
  "sources": {
    "S1": {"file": "docs/evidence/fr-b2/evidence/AAPL_2026-11-11/snapshot.txt", "description": "..."},
    "S2": {"file": "docs/evidence/fr-b2/evidence/AAPL_2026-11-11/snapshot_MISSING.txt", "description": "..."}
  }
}
```
`file` 是相对 `--base-dir`（默认当前目录 = 仓库根）的路径。

### 待查清单（`--claims`）
```json
{
  "claims": [
    {
      "id": "c1_valid",
      "report_span": {"line": 5, "snippet": "AAPL closed at **355.63** on 2026-11-11"},
      "citation": {"source_id": "S1", "source_line": 66, "expected_snippet": "| 2026-11-11 | 355.63 |"}
    }
  ]
}
```
- `report_span`：结论在报告中的定位，`line` 为行号，`snippet` 为该行必含的原文片段（**非空**）。
- `citation`：可选。含 `source_id`（来源表键）、`source_line`（1 基整数）、`expected_snippet`（该行必含文本）。
- 报告路径由 `--report` 统一传入，不写在清单里。

## 3. 完整运行命令（从仓库根）

```bash
python -m fr_b2.check_citations \
  --report docs/evidence/fr-b2/evidence/AAPL_2026-11-11/report/1_analysts/market.md \
  --sources fr_b2/sources.json \
  --claims fr_b2/claims.example.json \
  --out fr_b2/out/result.json
```
可选参数：`--base-dir`（解析证据相对路径的基准，默认 `.`）。
`--out` 指向任何输入文件（报告、来源表、清单，或来源表登记的证据文件）时拒绝写入并返回退出码 `2`，原文件保持不变。

## 4. 离线测试命令

```bash
python -m pytest fr_b2/tests -q
# 18 passed
```

测试覆盖：正确引用可定位原文；缺引用 / 格式错误 / 来源编号不存在 / 证据文件缺失 /
引用位置无效五类反例；仅行号无片段判 `claim_not_found`；不可读证据隔离到单条；
`--out` 与输入或证据冲突时拒绝且原文件不变。

## 5. AAPL 示例

- 报告：`docs/evidence/fr-b2/evidence/AAPL_2026-11-11/report/1_analysts/market.md` 第 5 行——
  "AAPL closed at **355.63** on 2026-11-11"。
- 证据：`docs/evidence/fr-b2/evidence/AAPL_2026-11-11/snapshot.txt` 第 66 行——
  `| 2026-11-11 | 355.63 |`（本次分析前独立调用官方
  `build_verified_market_snapshot("AAPL","2026-11-11")` 取得的核对证据）。
- 这是六条样本中的正例 `c1_valid`，可定位到报告原文与快照原文。

## 6. 预期结果（六条样本）

```
c1_valid            SUPPORTED
c2_missing_citation UNTRACEABLE (missing_citation)
c3_malformed_citation UNTRACEABLE (malformed_citation)
c4_unknown_source   UNTRACEABLE (unknown_source)
c5_missing_evidence UNTRACEABLE (missing_evidence)
c6_invalid_locator  UNTRACEABLE (invalid_locator)
SUMMARY total=6 supported=1 untraceable=5
```

更多细节（失败原因码、输入格式约束、复现步骤）见
[`docs/evidence/fr-b2/RUNBOOK.md`](../docs/evidence/fr-b2/RUNBOOK.md)。

## 7. 退出码与结果字段

引用检查命令正常完成时返回 `0`，包括发现 `UNTRACEABLE` 的情况。
自动化调用方应读取 JSON 的 `summary.untraceable` 和逐条 `reason` 判断检查发现。
拒绝用 `--out` 覆盖输入文件时返回 `2`；文件读取、解析等执行错误也会产生非零退出码。
`tests/test_review_followups.py` 对混合六条样本的退出码 `0` 有专门断言。

## 8. FR-B2 的验收范围

FR-B2 接收调用方提供的待查清单和引用，检查报告定位、来源登记、文件可读性、
证据行号和原文片段。`SUPPORTED` 的含义是引用可定位。
结论与证据之间的语义支撑性、计算正确性和模型自动生成引用需要分别评估。
本分支以 `FR-B2` 验收；需求表中的 `FR-B1` 还有关键字段自动附加引用等交付范围，
团队整合时需据实际完成情况更新追踪矩阵。

## 9. 保存证据的 SHA-256 校验

`docs/evidence/fr-b2/evidence-sha256.json` 登记了全部 25 份 AAPL 证据文件。
路径相对于该清单所在目录。命令可从仓库根目录运行：

```bash
python -m fr_b2.verify_evidence \
  --manifest docs/evidence/fr-b2/evidence-sha256.json
```

全部匹配返回 `0`；存在内容变化、文件缺失或不可读时返回 `1`；
清单格式或读取错误返回 `2`。默认 `pytest -q` 和 CI 都会运行这些离线校验测试。

指纹在 2026-11-20 审查补充时登记，参照提交为 `f80b28d`。
它核验保存文件相对登记值的完整性。采集时间、来源和运行方式见 provenance，
文件真实性还需结合这些运行记录和原始会话判断。

## 10. 给集成人员的文件

- `docs/evidence/fr-b2/ai-use-log.yaml` 记录原始开发与本轮审查修订的 AI 使用情况。
- [`integration-notes.md`](../docs/evidence/fr-b2/integration-notes.md)
  列出 CI、中央 AI-use log 和评测 manifest 的接入方法及尚需 E 同学确认的项目。
- 代码审查可先查看 `check_citations.py`、`verify_evidence.py`、`tests/` 和 `pyproject.toml`，
  再查看 `docs/evidence/fr-b2/` 的复现证据及 `transcripts/` 的 D5 会话。
