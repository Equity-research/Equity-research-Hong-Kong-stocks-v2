# 取数数据源索引（2026-07-02）

本文件记录本次取数所使用的数据源名称、地址及对应保存数据的文档名，供后续读取和更新。

## 数据文档与主要来源

| 保存数据的文档名 | 数据内容 | 数据源名称 | 数据源地址 |
|---|---|---|---|
| `data/daily_ipo_2026-07-02.csv` | 当日港股 IPO 名单、认购状态、截止日及预计上市日 | 富途资讯－新股资讯 | https://news.futunn.com/news-topics/172/stocks-ipo |
| `data/ipo_subscription_2026-07-02.csv` | 招股期实时推算认购倍数 | HKIPOx | https://hkipox.com/ |
| `data/hk_ipo_valuation_2026-07-02.csv` | 招股价、市值、财务数据、估值与可比公司 | HKIPOx | https://hkipox.com/ |
| `data/ipo_market_sentiment_2026-07-02.md` | 孖展认购、基石投资者、市场报道及公开讨论 | 新浪财经港股新股列表 | https://vip.stock.finance.sina.com.cn/q/view/hk_IPOList.php |
| `data/ipo_market_sentiment_2026-07-02.md` | 当日申购名单 | 新浪财经－2026-07-01 今日 16 股申购 | https://finance.sina.com.cn/stock/bxjj/2026-07-01/doc-iniffyth6341639.shtml |
| `data/ipo_market_sentiment_2026-07-02.md` | 新股孖展统计 | 证券之星－2026-07-01 新股孖展统计 | https://hk.stockstar.com/IG2026070100040998.shtml |
| `data/ipo_market_sentiment_2026-07-02.md` | 动态认购倍数 | HKIPOx | https://hkipox.com/ |
| `data/ipo_market_sentiment_2026-07-02.md` | 动态认购倍数补充 | SL886 港股 IPO 新股认购 | https://www.sl886.com/ipo/index?lsd=asc&lsort=pe_ratio&q=%2Fipo%2Findex&sort=Code |
| `data/ipo_market_sentiment_2026-07-02.md` | IPO 周报、公司招股资料与市场背景 | 新浪财经－港股 IPO 周报 | https://finance.sina.com.cn/stock/hkstock/hkzmt/2026-06-28/doc-inieyrin5986328.shtml |
| `data/ipo_market_sentiment_2026-07-02.md` | 同仁堂医养重新招股资料 | 新浪财经－同仁堂医养重启招股 | https://finance.sina.com.cn/cj/2026-06-27/doc-inievkwy1559089.shtml |
| `data/ipo_market_sentiment_2026-07-02.md` | Momenta 招股资料 | 新浪财经－Momenta 启动招股 | https://finance.sina.com.cn/stock/relnews/hk/2026-06-29/doc-inifaiss5443598.shtml |
| `data/ipo_market_sentiment_2026-07-02.md` | Momenta 基石投资者资料 | 新浪港股－14 家基石抢筹 | https://finance.sina.com.cn/stock/hkstock/2026-06-29/doc-iniezsvh7061273.shtml |
| `data/ipo_market_sentiment_2026-07-02.md` | 珞石机器人招股资料 | 新浪财经－珞石机器人正式招股 | https://finance.sina.com.cn/stock/hkstock/ggscyd/2026-06-30/doc-inifczzy1734396.shtml |
| `data/ipo_market_sentiment_2026-07-02.md` | 三环集团招股及基石阵容 | 新浪财经－三环集团招股及基石阵容 | https://finance.sina.com.cn/stock/hkstock/hkzmt/2026-06-30/doc-iniffivk1330359.shtml |
| `data/ipo_market_sentiment_2026-07-02.md` | 新股市场观点 | 雪球－七只新股简评 | https://xueqiu.com/4612256195/397599726 |
| `data/ipo_market_sentiment_2026-07-02.md` | Momenta、东方科脉打新观点 | 雪球－Momenta、东方科脉打新分析 | https://xueqiu.com/7111102454/397439894 |
| `data/ipo_market_sentiment_2026-07-02.md` | 立讯精密港股 IPO 讨论 | 雪球－立讯精密港股 IPO 讨论 | https://xueqiu.com/9875265866/395759792 |
| `data/ipo_market_sentiment_2026-07-02.md` | 鼎泰高科港股 IPO 讨论 | 雪球－鼎泰高科港股 IPO 讨论 | https://xueqiu.com/6869898602/396340439 |

## 估值文档使用的招股书及研究资料

以下资料均对应保存于 `data/hk_ipo_valuation_2026-07-02.csv` 的估值数据。

| 公司 | 数据源名称 | 数据源地址 |
|---|---|---|
| 同仁堂医养 | 香港交易所披露易－招股书 | https://www.hkexnews.hk/listedco/listconews/sehk/2026/0626/2026062600022_c.pdf |
| 东方科脉 | 财华社附件－研究资料 | https://images.finet.hk/attach/files/202606/5d9e6c15fd95bd58c4cc39545588ad11.pdf |
| 瑞为技术 | 财华社附件－研究资料 | https://images.finet.hk/attach/files/202606/4ec4e24b6aa7b30fd5bb4ff852e74ec3.pdf |
| 易控智驾 | 财华社附件－研究资料 | https://images.finet.hk/attach/files/202606/0975a815fae940348c0ea270c0b7191b.pdf |
| 易控智驾 | 香港交易所披露易－招股书 | https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0629/2026062900136_c.pdf |
| 基本半导体 | 华盛通资讯 | https://news.hstong.com/post/content/26062907314760052 |
| MOMENTA-W | 财华社附件－研究资料 | https://images.finet.hk/attach/files/202606/9c8fc14f67ffa67d755d3909eeb5647b.pdf |
| 珞石机器人 | 财华社附件－研究资料 | https://images.finet.hk/attach/files/202606/b5de49a1e90aee806853e7527e1f3aee.pdf |
| 珞石机器人 | 齐鲁国际－研究报告 | https://www.qlzq.com.hk/upload/20260320/20260320094702164.pdf |
| 立讯精密、三环集团 | 财华社附件－可比公司研究资料 | https://images.finet.hk/attach/files/202606/1b38b8281dc0b5237a08371a0c45360f.pdf |

## 读取说明

- CSV 文件可按表头字段直接读取；其中 `data_source`、`source_url` 或 `source_urls` 字段保留逐条来源。
- `source_urls` 中的多个地址使用竖线 `|` 分隔。
- 市场情绪资料及其引用上下文保存在 Markdown 文档中。
- 孖展和认购倍数属于动态数据，后续使用时应同时检查 `record_date` 和 `captured_at`。
