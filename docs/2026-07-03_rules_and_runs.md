# 2026-07-03 规则与跑数改动记录

记录时间：2026-07-03（Asia/Shanghai）

## 摘要

今天的改动主线有两条：

- 日报股票池改为依赖当日 IPO 清单，只纳入仍可申购、且尚未到预计上市日的项目。
- A+H 溢价改为按当日 A 股收盘价和 CNY/HKD 汇率自动生成，并在报告前覆盖评分输入。

本记录用于后续查询当天规则、跑数口径、生成产物和相关代码位置。

## 规则改动

### 当日 IPO 股票池过滤

- 新增 `data/daily_ipo_YYYY-MM-DD.csv` 作为每日报告的必备输入。
- 生成日报时读取同一天的 `daily_ipo` 清单。
- 只保留 `subscription_end_date > report_date` 的项目。
- 如果存在 `expected_listing_date`，还要求 `expected_listing_date > report_date`。
- 当天截止申购、已经截止申购、或已经到预计上市日的项目不进入当日报告。
- 缺少当日清单时，接口返回 409，提示先重新拉取当日 IPO 数据，避免混入旧股票池。

相关代码：

- `app/daily_ipo.py`
- `app/reporting.py`
- `app/main.py`
- `app/repository.py`

### 评分输入规范化

- 新增 `normalize_metrics()`，评分前统一规范化布尔值、数字和列表。
- 中文值如“有 / 无 / 是 / 否 / 设有 / 未设”等会转成布尔值。
- 百分比字符串可用于判断绿鞋等布尔字段是否存在。
- `cornerstone_investors` 支持按中文顿号、逗号、分号、换行拆成列表。
- `cornerstone_ratio` 转成数字。
- 如果有基石投资者列表或基石占比大于 0，会推断 `has_cornerstone=True`。
- 如果 `has_cornerstone=False`，则强制 `cornerstone_quality_good=False`，避免无基石时误加基石质量分。

相关代码：

- `app/scoring.py`
- `tests/test_scoring.py`

### A+H 溢价评分输入

- 新增 `data/ah_premium_YYYY-MM-DD.csv` 作为 A+H 溢价输入。
- A/H 溢价计算口径：

```text
A/H 溢价 = A股收盘价 × CNY/HKD / H股招股价 - 1
```

- 报告生成前调用 `apply_ah_premiums()`，把当日 A/H 溢价写入 IPO metrics，并重新计算评分。
- A/H 数据包括 A 股 ticker、A 股收盘价、CNY/HKD、溢价、来源和备注。
- 若当日行情抓取失败，脚本会回退最近一份 `ah_premium_YYYY-MM-DD.csv`，并在 `source` 标记 fallback，便于人工复核。

相关代码：

- `app/ah_premium.py`
- `app/database.py`
- `scripts/run_daily_report.py`

### 前端展示口径

- IPO 详情面板移除手动调整保存入口。
- 详情页保留发行资料、风险提示、评分详情等展示。
- 当日报告仍由后端按最新股票池和评分输入生成。

相关代码：

- `frontend/src/App.tsx`

## 跑数改动

### 统一跑数脚本

新增统一脚本：

```bash
.venv/bin/python scripts/run_daily_report.py --date 2026-07-03
```

脚本流程：

1. 确保存在 `data/daily_ipo_2026-07-03.csv`。
2. 如已有当日清单，则清洗掉已过申购截止或已到预计上市日的项目。
3. 如缺少当日清单，则基于最近历史清单生成当日清单，并剔除不再有效的项目。
4. 初始化或刷新本地 IPO 数据和评分。
5. 抓取或回退生成 `data/ah_premium_2026-07-03.csv`。
6. 将 A/H 溢价应用到评分输入。
7. 生成 Markdown、PDF、HTML 日报。

### 2026-07-03 当日股票池

当日有效 IPO 清单文件：

- `data/daily_ipo_2026-07-03.csv`

本次清洗后保留 9 个仍可申购项目：

- `02797.HK` 齐云山食品
- `03752.HK` 珞石机器人
- `00537.HK` 普源精电
- `02475.HK` 立讯精密
- `06951.HK` 三环集团
- `01377.HK` 鼎泰高科
- `02249.HK` 晶合集成
- `06745.HK` 滨化股份
- `02523.HK` 永康控股

相比旧版 16 个项目，已排除 2026-07-03 当天或之前截止申购的项目。

### 2026-07-03 A/H 溢价数据

当日 A/H 溢价文件：

- `data/ah_premium_2026-07-03.csv`

数据来源：

- Yahoo Finance chart API

当日记录：

| H股代码 | 公司 | A股代码 | H股招股价(HKD) | A股收盘价(CNY) | CNY/HKD | A/H溢价 |
|---|---|---|---:|---:|---:|---:|
| 00537.HK | 普源精电 | 688337.SS | 45.98 | 70.07 | 1.156 | 76.2% |
| 02475.HK | 立讯精密 | 002475.SZ | 63.28 | 65.19 | 1.156 | 19.1% |
| 06951.HK | 三环集团 | 300408.SZ | 100.30 | 151.10 | 1.156 | 74.1% |
| 01377.HK | 鼎泰高科 | 301377.SZ | 380.00 | 532.56 | 1.156 | 62.0% |
| 02249.HK | 晶合集成 | 688249.SS | 32.30 | 64.19 | 1.156 | 129.7% |
| 06745.HK | 滨化股份 | 601678.SS | 3.59 | 6.96 | 1.156 | 124.1% |

### 2026-07-03 报告产物

新口径报告：

- `ipo_daily_analysis_2026-07-03.md`
- `ipo_daily_analysis_2026-07-03.pdf`
- `ipo_daily_analysis_2026-07-03.html`

当前 Markdown 报告摘要：

- 共 9 个项目。
- 申购 1 个：三环集团。
- 观望 4 个：普源精电、鼎泰高科、晶合集成、滨化股份。
- 回避 4 个：珞石机器人、齐云山食品、立讯精密、永康控股。

旧口径对照报告：

- `ipo_daily_analysis_2026-07-03_v2.md`
- `ipo_daily_analysis_2026-07-03_v2.pdf`

旧口径仍包含 16 个项目，可用于对比“过滤已截止项目”前后的差异。

## 测试与文档

新增或更新测试：

- `tests/test_api.py`：补齐当日 `daily_ipo` 测试数据，报告生成改为指定 `report_date=2026-07-02`。
- `tests/test_scoring.py`：覆盖布尔值规范化、基石推断、绿鞋百分比字符串等评分输入场景。

文档更新：

- `README.md` 增加“每日报告数据要求”，说明每日 CSV、统一脚本、A/H 溢价文件和 fallback 口径。

## 后续查询关键词

- `2026-07-03`
- `daily_ipo_YYYY-MM-DD`
- `active_subscription_codes`
- `subscription_end_date > report_date`
- `expected_listing_date > report_date`
- `ah_premium_YYYY-MM-DD`
- `apply_ah_premiums`
- `normalize_metrics`
- `run_daily_report.py`
- `A/H 溢价`
- `Yahoo Finance chart API`
