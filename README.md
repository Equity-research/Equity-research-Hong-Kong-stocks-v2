# 港股 IPO 分析工具

本地研究演示工具：FastAPI + React + SQLite。首版只包含明确标记的样例数据，不构成投资建议。

## 启动

需要 Python 3.11+ 和 Node.js 20+：

```bash
chmod +x run.sh
./run.sh
```

浏览器访问 `http://127.0.0.1:5173`，API 文档位于 `http://127.0.0.1:8000/docs`。

公网部署时应设置 `STOCK_ADMIN_API_KEY`。设置后，评分调整、暗盘录入、报告生成和数据刷新等写接口必须携带 `X-Admin-Key`：

systemd 部署可将密钥写入仅 root 可读的 `/etc/stock/stock.env`，服务和定时任务都会读取该文件：

```bash
sudo install -d -m 700 /etc/stock
printf 'STOCK_ADMIN_API_KEY=%s\n' '替换为高强度随机密钥' | sudo tee /etc/stock/stock.env >/dev/null
sudo chmod 600 /etc/stock/stock.env
sudo systemctl daemon-reload
sudo systemctl restart stock-api
```

```bash
curl -H "X-Admin-Key: $STOCK_ADMIN_API_KEY" -X POST http://127.0.0.1:8080/api/data-refresh
```

浏览器管理操作可在当前标签页的开发者控制台中临时设置密钥，关闭标签页后自动清除：

```js
sessionStorage.setItem('stock-admin-api-key', '替换为实际密钥')
```

也可分别启动：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python main.py

cd frontend
npm install
npm run dev
```

## 测试

```bash
. .venv/bin/activate
pytest
cd frontend && npm test && npm run typecheck && npm run build
```

评分阈值和权重集中在 `scoring_rules.yaml`；SQLite 数据保存在 `data/hk_ipo.db`，生成内容写入数据库并通过 API 下载。

## 每日报告数据要求

生成日报前必须先更新当日 IPO 清单：

```text
data/daily_ipo_YYYY-MM-DD.csv
```

报告生成会读取与 `report_date` 同一天的清单，只纳入 `subscription_end_date > report_date` 且尚未到预计上市日的项目。当天截止或已经超过申购截止时间的项目不再进入报告；若缺少当天清单，接口会拒绝生成日报并提示先重新拉取当日 IPO 数据，避免把已经截止申购或已经上市的旧项目混入当天报告。

可用统一脚本跑完整流程：

```bash
.venv/bin/python scripts/run_daily_report.py --date 2026-07-03
```

脚本会生成/更新当日 `daily_ipo_YYYY-MM-DD.csv`，清洗掉已过申购截止的项目，重新初始化评分，写出同日期的 Markdown、PDF 和 HTML 报告。后续每天跑完数据后，HTML 报告会同步使用最新股票池。

脚本也会同步当日招股书目录：

```text
prospectuses/YYYY-MM-DD/
```

同步规则与当日申购股票池一致：仍在 `daily_ipo_YYYY-MM-DD.csv` 的 PDF 会保留，已经不在当日申购数据里的 PDF 会从当天目录删除；新增股票会先复用历史目录中同代码招股书，找不到时再从 HKIPOx 个股页的“招股书”链接下载新 PDF。若新增股票无法找到或下载招股书，脚本会停止并提示需要人工复核。

脚本还会全量生成当日申购倍数快照，并在评分前覆盖数据库中的 `subscription_multiple`：

```text
data/ipo_subscription_YYYY-MM-DD.csv
```

当日仍可申购项目如果缺少申购倍数，脚本会停止生成日报，避免沿用旧快照。

A+H 公司会同步生成：

```text
data/ah_premium_YYYY-MM-DD.csv
```

脚本会抓取 A 股最新日线收盘价和 CNY/HKD 汇率，按 `A股收盘价 × CNY/HKD / H股招股价 - 1` 计算 A/H 溢价，并在生成报告前覆盖评分输入。若当日行情抓取失败，会回退最近一份 `ah_premium_YYYY-MM-DD.csv` 并在 `source` 字段标记，方便人工复核。

## 一键跑全量数据

推荐直接用一键脚本，它会自动准备 `.venv`、安装依赖，并显示每个数据阶段的进度：

```bash
./scripts/run_all_data.sh
```

默认使用当天日期。也可以指定日期：

```bash
./scripts/run_all_data.sh 2026-07-03
```

脚本默认在依赖步骤之间等待 2 秒，方便观察联网抓取和数据库写入进度；如需取消等待：

```bash
WAIT_SECONDS=0 ./scripts/run_all_data.sh 2026-07-03
```

底层 Python 脚本也支持同样的进度参数：

```bash
.venv/bin/python scripts/run_daily_report.py --date 2026-07-03 --wait 0
```
