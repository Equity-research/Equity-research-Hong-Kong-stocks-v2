#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/stock}"
SERVICE_NAME="${SERVICE_NAME:-stock-api}"
PORT="${PORT:-8080}"
BRANCH="${BRANCH:-main}"
REPORT_DATE="${1:-$(TZ=Asia/Shanghai date +%F)}"
WAIT_SECONDS="${WAIT_SECONDS:-0}"
APP_USER="${APP_USER:-}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-10}"
CURL_MAX_TIME="${CURL_MAX_TIME:-180}"

service_user() {
  local configured_user pid_user pid
  configured_user="$(systemctl show -p User --value "$SERVICE_NAME" 2>/dev/null || true)"
  if [ -n "$configured_user" ]; then
    echo "$configured_user"
    return
  fi
  pid="$(systemctl show -p MainPID --value "$SERVICE_NAME" 2>/dev/null || true)"
  if [ -n "$pid" ] && [ "$pid" != "0" ]; then
    pid_user="$(ps -o user= -p "$pid" 2>/dev/null | awk '{print $1}')"
    if [ -n "$pid_user" ]; then
      echo "$pid_user"
      return
    fi
  fi
  id -un
}

curl_json_to_file() {
  local label="$1"
  local url="$2"
  local output_path="$3"

  if curl --connect-timeout "$CURL_CONNECT_TIMEOUT" --max-time "$CURL_MAX_TIME" -fsS "$url" >"$output_path"; then
    echo "${label} saved to ${output_path}"
  else
    local status=$?
    echo "WARNING: ${label} failed or timed out after ${CURL_MAX_TIME}s, continuing. curl exit=${status}"
    rm -f "$output_path"
  fi
}

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
  APP_USER="${APP_USER:-$(service_user)}"
  chown -R "$APP_USER":"$APP_USER" data prospectuses output 2>/dev/null || true
  chown "$APP_USER":"$APP_USER" ipo_daily_analysis.html ipo_daily_analysis.md ipo_daily_analysis.pdf 2>/dev/null || true
fi
chmod -R a+rwX data prospectuses output
chmod a+rw ipo_daily_analysis.html ipo_daily_analysis.md ipo_daily_analysis.pdf 2>/dev/null || true

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
curl --connect-timeout "$CURL_CONNECT_TIMEOUT" --max-time 30 -fsS "http://127.0.0.1:${PORT}/api/health"
echo

echo "==> 8. Run A-share sentiment data"
curl_json_to_file \
  "A-share sentiment" \
  "http://127.0.0.1:${PORT}/api/a-shares/sentiment?record_date=${REPORT_DATE}&refresh=true" \
  "/tmp/a_share_sentiment_${REPORT_DATE}.json"

echo "==> 9. Run US market data"
curl_json_to_file \
  "US market dashboard" \
  "http://127.0.0.1:${PORT}/api/us-market/dashboard?record_date=${REPORT_DATE}&refresh=true" \
  "/tmp/us_market_${REPORT_DATE}.json"

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
curl --connect-timeout "$CURL_CONNECT_TIMEOUT" --max-time 30 -fsS "http://127.0.0.1:${PORT}/api/reports"
echo

echo "==> 11. Service status"
systemctl --no-pager --lines=20 status "$SERVICE_NAME"

echo "==> Data job complete"
