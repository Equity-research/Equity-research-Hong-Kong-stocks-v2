#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/stock}"
SERVICE_NAME="${SERVICE_NAME:-stock-api}"
PORT="${PORT:-8080}"
BRANCH="${BRANCH:-main}"
REPORT_DATE="${1:-$(TZ=Asia/Shanghai date +%F)}"
WAIT_SECONDS="${WAIT_SECONDS:-0}"
APP_USER="${APP_USER:-$(id -un)}"

echo "==> Run date: ${REPORT_DATE}"
echo "==> App dir: ${APP_DIR}"
echo "==> Branch: ${BRANCH}"

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: APP_DIR not found: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

echo "==> 0. Update code"
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
if [ "$(id -u)" = "0" ]; then
  git config --system --add safe.directory "$APP_DIR" 2>/dev/null || true
fi

git fetch origin "$BRANCH"

STASH_CREATED=0
if [ -n "$(git status --porcelain)" ]; then
  echo "Local changes detected; stashing before updating ${BRANCH}."
  git stash push --include-untracked -m "data-job-autostash ${REPORT_DATE} $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  STASH_CREATED=1
fi

git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [ "$STASH_CREATED" = "1" ]; then
  echo "Previous local changes were preserved in git stash."
fi

echo "==> 1. Prepare writable directories"
mkdir -p data prospectuses output
if [ "$(id -u)" = "0" ]; then
  chown -R "$APP_USER":"$APP_USER" data prospectuses output ipo_daily_analysis.html ipo_daily_analysis.md ipo_daily_analysis.pdf 2>/dev/null || true
fi
chmod -R u+rwX data prospectuses output

echo "==> 2. Prepare Python environment"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

echo "==> 3. Install/update Python dependencies"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "==> 4. Build frontend"
if command -v pnpm >/dev/null 2>&1; then
  (cd frontend && pnpm install --frozen-lockfile && pnpm build)
else
  (cd frontend && npm install && npm run build)
fi

echo "==> 5. Run HK IPO data and daily report"
WAIT_SECONDS="$WAIT_SECONDS" ./scripts/run_all_data.sh "$REPORT_DATE"

echo "==> 6. Restart service"
systemctl restart "$SERVICE_NAME"

echo "==> 7. Wait for API"
sleep 3
curl -fsS "http://127.0.0.1:${PORT}/api/health"
echo

echo "==> 8. Run A-share sentiment data"
curl -fsS "http://127.0.0.1:${PORT}/api/a-shares/sentiment?record_date=${REPORT_DATE}&refresh=true" \
  >"/tmp/a_share_sentiment_${REPORT_DATE}.json"
echo "A-share sentiment saved to /tmp/a_share_sentiment_${REPORT_DATE}.json"

echo "==> 9. Run US market data"
curl -fsS "http://127.0.0.1:${PORT}/api/us-market/dashboard?record_date=${REPORT_DATE}&refresh=true" \
  >"/tmp/us_market_${REPORT_DATE}.json"
echo "US market dashboard saved to /tmp/us_market_${REPORT_DATE}.json"

echo "==> 10. Verify generated files"
echo "--- HK IPO files ---"
ls -lh \
  "data/daily_ipo_${REPORT_DATE}.csv" \
  "data/ipo_subscription_${REPORT_DATE}.csv" \
  "data/ah_premium_${REPORT_DATE}.csv" 2>/dev/null || true

echo "--- A-share files ---"
ls -lh \
  "data/a_share_market_${REPORT_DATE}.csv" \
  "data/a_share_hot_words_${REPORT_DATE}.csv" \
  "data/a_share_hot_sectors_${REPORT_DATE}.csv" 2>/dev/null || true

echo "--- US market files ---"
ls -lh \
  "data/us_market_news_${REPORT_DATE}.json" 2>/dev/null || true

echo "--- Reports API ---"
curl -fsS "http://127.0.0.1:${PORT}/api/reports"
echo

echo "==> 11. Service status"
systemctl --no-pager --lines=20 status "$SERVICE_NAME"

echo "==> Data job complete"
