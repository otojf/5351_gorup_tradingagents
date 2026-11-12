# RUNBOOK — FR-B2 报告结论引用检查

本仓库是 CS5351 团队 TradingAgents（上游 v0.7.1）。FR-B2 的全部交付：

| 路径 | 内容 |
|---|---|
| `fr_b2/check_citations.py` | 检查器源码 + 命令行入口（仅标准库，离线） |
| `fr_b2/sources.json` | 来源表（S1 真实快照，S2 刻意缺失文件） |
| `fr_b2/claims.example.json` | 六条样本清单 |
| `fr_b2/tests/test_check_citations.py` | 12 条离线测试 |
| `fr_b2/conftest.py` | 让仓库根可导入 `fr_b2` |
| `docs/evidence/fr-b2/evidence/AAPL_2026-11-11/` | AAPL 2026-11-11 复现证据（报告 + 快照 + 决策 + 运行记录） |
| `docs/evidence/fr-b2/provenance.md` | 版本、依赖、会话审批记录 |
| `docs/evidence/fr-b2/requirements.lock.txt` | 依赖锁定快照 |
| `scripts/reproduce_aapl_2026-11-11.py` | 复现脚本 |

证据相对路径以**仓库根**为基准（`base_dir`），因此 `report/1_analysts/market.md` 与 `snapshot.txt` 均可直接定位。

## 1. 环境与基线（可选，真实运行才需要）

```bash
python -m venv .venv && source .venv/bin/activate   # Python >= 3.11
pip install -e ".[dev]"
pytest -q                                           # 官方套件（-m "not integration"）
```

真实分析凭据仅放本地 `.env`（已被 .gitignore 忽略），本仓库只记录非敏感配置：
```
TRADINGAGENTS_LLM_PROVIDER=deepseek
TRADINGAGENTS_LLM_BACKEND_URL=https://llm.cs.cityu.edu.hk/v1
TRADINGAGENTS_QUICK_THINK_LLM=CS5351/DeepSeek-V4-Flash
TRADINGAGENTS_DEEP_THINK_LLM=CS5351/DeepSeek-V4-Flash
DEEPSEEK_API_KEY=<your key>
```
复现本次 AAPL 分析（可选，会写回证据目录）：
```bash
python scripts/reproduce_aapl_2026-11-11.py
```

## 2. FR-B2 检查（从仓库根运行，离线）

```bash
python -m fr_b2.check_citations \
  --report docs/evidence/fr-b2/evidence/AAPL_2026-11-11/report/1_analysts/market.md \
  --sources fr_b2/sources.json \
  --claims fr_b2/claims.example.json \
  --out fr_b2/out/result.json
```

预期摘要：
```
- c1_valid: SUPPORTED -> docs/evidence/fr-b2/evidence/AAPL_2026-11-11/snapshot.txt:66
    report: docs/evidence/fr-b2/evidence/AAPL_2026-11-11/report/1_analysts/market.md:5
    source: | 2026-11-11 | 355.63 |
- c2_missing_citation: UNTRACEABLE (missing_citation)
- c3_malformed_citation: UNTRACEABLE (malformed_citation)
- c4_unknown_source: UNTRACEABLE (unknown_source)
- c5_missing_evidence: UNTRACEABLE (missing_evidence)
- c6_invalid_locator: UNTRACEABLE (invalid_locator)
SUMMARY total=6 supported=1 untraceable=5
```

### 离线验收测试

```bash
python -m pytest fr_b2/tests -q
# 12 passed
```

### 失败原因码
- `claim_not_found` — `report_span` 缺失/非法，或只给行号无原文片段，或片段不在该行
- `missing_citation` — 结论无引用
- `malformed_citation` — 引用字段缺失或类型错误（如 `source_line` 非整数）
- `unknown_source` — `source_id` 不在来源表
- `missing_evidence` — 来源指向的证据文件不存在
- `unreadable_evidence` — 证据存在但无法按 UTF-8 读取（仅该条失败）
- `invalid_locator` — 行号越界，或该行不含 `expected_snippet`

`SUPPORTED` 仅当全部检查通过；其余一律 `UNTRACEABLE`，不计入 `supported`。
`report_span` 必须同时给出行号与**非空**原文片段。

`--out` 若与 `--report`/`--sources`/`--claims` 或来源表登记的证据文件（按 `--base-dir` 解析）指向同一文件，拒绝写入（退出码 2），原文件不变。

## 3. 输入格式

来源表（`--sources`）：
```json
{"sources": {"S1": {"file": "docs/evidence/fr-b2/evidence/AAPL_2026-11-11/snapshot.txt"},
             "S2": {"file": "docs/evidence/fr-b2/evidence/AAPL_2026-11-11/snapshot_MISSING.txt"}}}
```

样本清单（`--claims`）：
```json
{"claims": [{
  "id": "c1_valid",
  "report_span": {"line": 5, "snippet": "AAPL closed at **355.63** on 2026-11-11"},
  "citation": {"source_id": "S1", "source_line": 66, "expected_snippet": "| 2026-11-11 | 355.63 |"}
}]}
```
`report_span` 只含行号与原文片段（报告路径由 `--report` 统一传入）。

## 4. 证据说明

`docs/evidence/fr-b2/evidence/AAPL_2026-11-11/snapshot.txt` 为本次分析**前**独立调用官方
`tradingagents.dataflows.vendors.yahoo.snapshot.build_verified_market_snapshot("AAPL","2026-11-11")`
取得的核对证据：文本、可按行号定位，与真实分析同一会话、同一数据源。
