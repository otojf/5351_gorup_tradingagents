# Provenance — TradingAgents 复现

## 版本锁定
- 远程仓库: https://github.com/TauricResearch/TradingAgents.git
- Tag: `v0.7.1`
- 锁定提交 (完整 SHA): `c4544913a14ed3df5f1ed7b9e8483270ce20682a`
- `git describe --tags`: `v0.7.1`
- clone 时间: 2026-11-12 18:35 CST
- 本地路径: `upstream/`（工作区根 `/Users/parsifal/Desktop/softnew`）

## 环境
- 管理器: conda
- 环境名: `ta-frb2`
- Python: 3.13.16
- 安装方式（按官方 CI `.github/workflows/ci.yml`）: `pip install -e ".[dev]"`
- 依赖快照: `META/requirements.lock.txt`（`pip freeze`）

## 基线检查
- `import tradingagents, cli.main` -> OK, version 0.7.1（对应 CI 的 clean-install smoke 语义）
- `pytest -q`（默认 `-m "not integration"`）:
  - **1412 passed, 1 skipped, 1 deselected, 100 subtests passed, 24 warnings in 10.56s**
  - 跳过项: `tests/test_bedrock_provider.py:74` — 缺少可选依赖 `langchain_aws`（bedrock extra 未安装，符合预期）
  - deselected: 1（integration 标记用例被默认过滤）

## 分析运行设定
- 选股: AAPL
- 分析日期: **2026-11-11**（固定）
  - 运行时刻 2026-11-12 18:39 CST / 约 11-12 05:39 美东，11-12 当日尚未收盘
  - 最近已收盘且日线完整的交易日为 2026-11-11（yfinance 已核对存在完整 OHLCV）
- LLM provider: deepseek（CityU 网关）
- backend_url: https://llm.cs.cityu.edu.hk/v1（非敏感）
- quick/deep model: CS5351/DeepSeek-V4-Flash
- API key: 存放于 `upstream/.env` 的 `DEEPSEEK_API_KEY`（已被 .gitignore 忽略，不入库、不打印）

## 实际运行（真实分析）
- 运行时间: 2026-11-12 19:09 CST
- 命令: `conda run -n ta-frb2 python scripts/run_baseline.py`（脚本位于工作区 `scripts/`，内部 `os.chdir(upstream)` 以加载 upstream/.env）
- 调用: `TradingAgentsGraph(debug=True, config=build_default_config())` + `propagate("AAPL","2026-11-11")` + `save_reports()`
- 分析员: market, social, news, fundamentals；debate 1 轮，risk 1 轮
- 结果决策: **Hold**
- 数据缺失/说明:
  - `macro_data=fred` 未配置 `FRED_API_KEY`，宏观数据可能不可得（不阻断运行）
  - `prediction_markets=polymarket` 按默认开启
  - 公司新闻走 yfinance 搜索（README 说明 Yahoo 新闻 feed 波动）
  - 本次运行完整跑通，未中断

## 证据文件（`evidence/AAPL_2026-11-11/`）
- `report/complete_report.md` / `.html`：原版完整报告（含全部分区）
- `report/1_analysts/{market,sentiment,news,fundamentals}.md` 等原始分区
- `market_report.md` / `sentiment_report.md` / `news_report.md` / `fundamentals_report.md` / `investment_plan.md` / `trader_investment_plan.md` / `final_trade_decision.md`：从 state 导出的单文件副本
- `snapshot.txt`：本次分析日（2026-11-11）官方验证行情快照，**文本、67 行、可用行号定位**
- `decision.txt`：`Hold`
- `run_settings.json`：本次运行设置（provider/model/vendors，无密钥）
- `run_log.json`：运行元数据

### 快照取得方式说明
本次快照通过**独立调用官方模块** `tradingagents.dataflows.vendors.yahoo.snapshot.build_verified_market_snapshot("AAPL","2026-11-11",look_back_days=30)` 生成（与 agents 使用的同一函数/同一数据源），保存为 `snapshot.txt`。取得时间与真实分析同一次会话（19:07 生成快照，19:09 完成分析），数据落在最近已收盘交易日，未受后续行情影响。

## 会话审批记录
1. 复现计划：已批准（v0.7.1 @ c4544913，AAPL，2026-11-11，CityU DeepSeek）。
2. 基线审查：通过（报告 + snapshot.txt + 真实引用对应关系已展示）。
3. FR-B2 测试设计：按修订通过（source_id/source_line/expected_snippet + --sources；report_span 仅行号+片段；6 条混合样本；独立 claim_not_found 测试）。
4. FR-B2 实现：**已批准**（2026-11-12，用户批准编写 fr_b2/check_citations.py）。
