# 港股 IPO 分析工具

本地研究演示工具：FastAPI + React + SQLite。首版只包含明确标记的样例数据，不构成投资建议。

## 启动

需要 Python 3.11+ 和 Node.js 20+：

```bash
chmod +x run.sh
./run.sh
```

浏览器访问 `http://127.0.0.1:5173`，API 文档位于 `http://127.0.0.1:8000/docs`。

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

