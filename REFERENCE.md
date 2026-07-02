# 港股 IPO 分析工具 · 参考手册

> 每次跑数据、改规则前先看一遍本文档。  
> 评分规则在 `scoring_rules.yaml`，改规则前记得备份到 `backups/`。

---

## 一、项目概览

| 项目 | 说明 |
|---|---|
| 技术栈 | FastAPI + React + SQLite |
| Python | 3.11+ |
| Node.js | 20+ |
| 数据库 | `hk_ipo.db`（SQLite，在 `data/` 下） |

### 启动

```bash
./run.sh
# 前端：http://127.0.0.1:5173
# API：http://127.0.0.1:8000/docs
```

也可分别启动：

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python main.py
```

```bash
cd frontend && npm install && npm run dev
```

### 测试

```bash
. .venv/bin/activate
pytest
cd frontend && npm test && npm run typecheck && npm run build
```

---

## 二、数据文件索引

### 2.1 核心数据文件（`data/` 目录）

| 文件 | 内容 | 来源 | 格式 |
|---|---|---|---|
| `data/daily_ipo_2026-07-02.csv` | 当日港股 IPO 名单、认购状态、截止日、预计上市日 | 富途资讯 | CSV |
| `data/ipo_subscription_2026-07-02.csv` | 招股期实时认购倍数（截至 10:34 CST 的推算值） | HKIPOx | CSV |
| `data/hk_ipo_valuation_2026-07-02.csv` | 招股价、市值、PE/PS、可比公司 | HKIPOx | CSV |
| `data/ipo_market_sentiment_2026-07-02.md` | 孖展认购、基石投资者、市场报道、公开讨论 | 新浪财经 / 雪球 / HKIPOx / SL886 | Markdown |
| `data/data_sources_2026-07-02.md` | 数据源索引（源→文件对应关系） | — | Markdown |

### 2.2 招股书（`prospectuses/` 目录）

按日期组织，格式 `prospectuses/yyyy-mm-dd/`：

```
prospectuses/2026-07-02/
├── 00537_普源精电_招股书.pdf
├── 01377_鼎泰高科_招股书.pdf
├── 01770_东方科脉_招股书.pdf
├── 02249_晶合集成_招股书.pdf
├── 02475_立讯精密_招股书.pdf
├── 02523_永康控股_招股书.pdf
├── 02667_同仁堂医养_招股书.pdf
├── 02797_齐云山食品_招股书.pdf
├── 03752_珞石机器人_招股书.pdf
├── 06745_滨化股份_招股书.pdf
├── 06880_MOMENTA-W_招股书.pdf
├── 06951_三环集团_招股书.pdf
├── 07656_瑞为技术_招股书.pdf
├── 07687_易控智驾_招股书.pdf
├── 08090_宝盖新材_招股书.pdf
└── 09971_基本半导体_招股书.pdf
```

命名规则：`{股票代码}_{公司简称}_招股书.pdf`

### 2.3 认购倍数数据（`data/ipo_subscription_2026-07-02.csv`）

字段：`record_date`、`captured_at`、`stock_code`、`company_name`、`subscription_multiple`、`status`、`subscription_end_date`、`data_type`、`data_source`、`source_url`

> ⚠️ 认购倍数是招股期实时推算值，不是最终超购倍数。数据截止 `2026-07-02 10:34:00 CST`。

### 2.4 估值数据（`data/hk_ipo_valuation_2026-07-02.csv`）

字段：`record_date`、`stock_code`、`company_name`、`industry`、`subscription_end_date`、`expected_listing_date`、`offer_price_hkd`、`post_ipo_market_cap_hkd_100m`、`financial_period`、`revenue_rmb_100m`、`net_profit_rmb_100m`、`ipo_pe_x`、`ipo_ps_x`、`peer_companies`、`peer_pe_x`、`peer_ps_x`、`valuation_basis`、`data_quality`、`source_urls`、`notes`

> `source_urls` 中多个地址用 `|` 分隔。

---

## 三、评分规则（`scoring_rules.yaml`）

### 3.1 概况

- **版本**：v2
- **总分**：10 分制
- **评级**：
  - ≥8 分：**申购**
  - 4–7.9 分：**观望**
  - <4 分：**回避**
- **调整**：人工调整范围 -1 ~ +1，调整理由 ≥10 字

### 3.2 评分维度与权重

| 维度 | 权重 | 计分方式 |
|---|---|---|
| 基石投资者 | 1 | 有基石 = 1 分 |
| 基石质量 | 1 | 具名高质量机构（GIC/富达/贝莱德等）= 1 分；需满足「有基石」前提 |
| 绿鞋机制 | 1 | 封面明确「超额配股权」= 1 分 |
| 公开申购倍数 | 3 | ≥100x → 3 分，≥50x → 2 分，≥10x → 1 分，<10x → 0 分 |
| 估值吸引力 | 3 | A+H 用 A/H 溢价，非 A+H 用同业 PS 折价 |
| 保荐人及历史表现 | 1 | 中金/中信/华泰/国泰海通/德银/高盛/汇丰等 = 1 分 |

### 3.3 估值吸引力分档

**A/H 溢价（A+H 公司）：**
- >70% → 3 分
- >50% → 2 分
- >30% → 1 分
- 否则 → 0 分

**同业 PS 折价（非 A+H 公司）：**
- IPO PS 比可比公司 PS 中位数低 >30% → 3 分
- 低 ≥10% → 2 分
- 低 >0% → 1 分
- 否则 → 0 分

### 3.4 保守假设（缺失计 0 分）

评分脚本在字段缺失时默认计 0 分，因此结果天然偏保守。以下情况会导致特定维度计 0：

1. 非 A+H 公司估值折价仅在 IPO 倍数与同行倍数能统一比较时计分
2. A+H 公司缺少同日 A 股价格 → A/H 折溢价计 0
3. 「保荐人质量良好」仅确认到主要机构时计 1 分
4. 「基石质量良好」仅确认到具名高质量机构时计 1 分；仅知有基石但名单不足 → 质量项计 0
5. 绿鞋仅在封面明确「超额配股权」时计 1 分；发售量调整权 ≠ 绿鞋

---

## 四、分析产物

| 文件 | 说明 |
|---|---|
| `ipo_daily_analysis_2026-07-02.md` | 当日 IPO 分析报告（含评分表、资金分配策略） |
| `ipo_daily_analysis_2026-07-02.html` | HTML 版分析报告 |

---

## 五、每次跑数据前必查清单

- [ ] 确认当前日期，数据文件日期是否匹配（文件名中的 `yyyy-mm-dd`）
- [ ] 检查 `scoring_rules.yaml` 版本号和规则是否最新
- [ ] 改规则前先在 `backups/` 中备份 `scoring_rules.yaml`
- [ ] 确认数据源可访问：富途资讯 / HKIPOx / 新浪财经 / SL886
- [ ] 确认招股书已下载到 `prospectuses/{date}/`
- [ ] 认购倍数文件中的 `captured_at` 时间是否合理（是否过时）
- [ ] 估值 CSV 中的 `data_quality` 字段是否有「未核验」项
- [ ] 运行 `pytest` 确认评分脚本无报错
- [ ] 看完本文档

---

## 六、关键数据源地址

| 数据源 | URL |
|---|---|
| 富途新股资讯 | https://news.futunn.com/news-topics/172/stocks-ipo |
| HKIPOx（认购倍数+估值） | https://hkipox.com/ |
| 新浪财经港股新股列表 | https://vip.stock.finance.sina.com.cn/q/view/hk_IPOList.php |
| SL886 新股认购 | https://www.sl886.com/ipo/index |
| 香港交易所披露易 | https://www.hkexnews.hk/ |

---

## 七、命名约定

- 数据文件：`{type}_{date}.{ext}`，例 `ipo_subscription_2026-07-02.csv`
- 招股书：`prospectuses/{date}/{stock_code}_{company}_招股书.pdf`
- 分析报告：`ipo_daily_analysis_{date}.md`
- 备份：`backups/` 目录下，保持原文件名或加日期后缀
