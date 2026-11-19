# FR-B2 — 报告结论引用检查（Citation Traceability Checker）

检查报告中的每一条结论是否能把引用追溯到同次运行证据里的原文。引用缺失、
格式错误、来源编号不存在、证据文件缺失，或引用位置在证据中找不到原文时，该结论标为
`UNTRACEABLE`，并从 `supported` 统计中剔除。仅当全部引用都解析成功才标 `SUPPORTED`。

- 入口：`fr_b2/check_citations.py`（`python -m fr_b2.check_citations`）
- 只依赖 Python 标准库，**离线**运行，不调用模型、不联网、不 import TradingAgents 内部模块。
- 对应需求：`docs/req/requirements-options.yaml` 中的 `FR-B2`（Owner B：结论可信）。

## 1. 判定结果

| 状态 | 含义 |
|---|---|
| `SUPPORTED` | 所有引用都解析到证据原文；计入 `supported` |
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
# 12 passed
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
