#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPORT_DATE="${1:-$(date +%F)}"
WAIT_SECONDS="${WAIT_SECONDS:-2}"

echo "[1/4] 准备 Python 虚拟环境"
./scripts/prepare_writable_paths.sh

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

echo "[2/4] 安装/更新 Python 依赖"
.venv/bin/python -m pip install -r requirements.txt

echo "[3/4] 跑全量 IPO 数据，日期=${REPORT_DATE}，阶段等待=${WAIT_SECONDS}s"
.venv/bin/python scripts/run_daily_report.py --date "$REPORT_DATE" --wait "$WAIT_SECONDS"

echo "[4/4] 完成"
echo "输出文件："
echo "  ipo_daily_analysis.md"
echo "  ipo_daily_analysis.pdf"
echo "  ipo_daily_analysis.html"
