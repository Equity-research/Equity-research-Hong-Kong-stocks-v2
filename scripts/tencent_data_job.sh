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
GIT_COMMAND_TIMEOUT="${GIT_COMMAND_TIMEOUT:-90}"
GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=5 -o ServerAliveCountMax=2}"
RUN_DEPLOY_STEPS="${RUN_DEPLOY_STEPS:-0}"
JOB_LOG_DIR="${JOB_LOG_DIR:-${APP_DIR}/output/data-job-logs}"
LOCK_FILE="${LOCK_FILE:-/tmp/stock-data-refresh.lock}"
STOCK_ADMIN_API_KEY="${STOCK_ADMIN_API_KEY:-}"
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND

ADMIN_HEADER_ARGS=()
if [ -n "$STOCK_ADMIN_API_KEY" ]; then
  ADMIN_HEADER_ARGS=(-H "X-Admin-Key: ${STOCK_ADMIN_API_KEY}")
fi

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

  echo "Requesting ${label}; max ${CURL_MAX_TIME}s: ${url}"
  if curl "${ADMIN_HEADER_ARGS[@]}" --connect-timeout "$CURL_CONNECT_TIMEOUT" --max-time "$CURL_MAX_TIME" -fsS "$url" >"$output_path"; then
    echo "${label} saved to ${output_path}"
  else
    local status=$?
    echo "WARNING: ${label} failed or timed out after ${CURL_MAX_TIME}s, continuing. curl exit=${status}"
    rm -f "$output_path"
  fi
}

run_timed() {
  local label="$1"
  local seconds="$2"
  shift 2

  echo "${label} (timeout ${seconds}s)"
  if command -v timeout >/dev/null 2>&1; then
    timeout --preserve-status "$seconds" "$@"
  else
    "$@"
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

mkdir -p "$JOB_LOG_DIR"
LOG_FILE="${JOB_LOG_DIR}/data-job-${REPORT_DATE}-$(date +%Y%m%d%H%M%S).log"

exec 9>"$LOCK_FILE"
if command -v flock >/dev/null 2>&1; then
  if ! flock -n 9; then
    echo "Another stock data refresh is already running. Lock: ${LOCK_FILE}"
    exit 75
  fi
fi

exec > >(tee -a "$LOG_FILE") 2>&1
echo "==> Log file: ${LOG_FILE}"
echo "==> Started at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [ "$RUN_DEPLOY_STEPS" = "1" ]; then
  echo "==> 0. Update code"
  git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
  if [ "$(id -u)" = "0" ]; then
    git config --system --add safe.directory "$APP_DIR" 2>/dev/null || true
  fi

  STASH_CREATED=0
  if run_timed "Fetching origin/${BRANCH}" "$GIT_COMMAND_TIMEOUT" git fetch origin "$BRANCH"; then
    echo "Checking local changes before pulling ${BRANCH}."
    if [ -n "$(git status --porcelain)" ]; then
      echo "Local changes detected; stashing before updating ${BRANCH}."
      run_timed "Stashing local changes" "$GIT_COMMAND_TIMEOUT" git stash push --include-untracked -m "data-job-autostash ${REPORT_DATE} $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      STASH_CREATED=1
    fi

    run_timed "Checking out ${BRANCH}" "$GIT_COMMAND_TIMEOUT" git checkout "$BRANCH"
    run_timed "Pulling origin/${BRANCH}" "$GIT_COMMAND_TIMEOUT" git pull --ff-only origin "$BRANCH"
  else
    echo "WARNING: git fetch origin/${BRANCH} failed or timed out after ${GIT_COMMAND_TIMEOUT}s; continuing with existing local checkout."
  fi

  if [ "$STASH_CREATED" = "1" ]; then
    echo "Previous local changes were preserved in git stash."
  fi
else
  echo "==> 0. Skip deploy steps; set RUN_DEPLOY_STEPS=1 to pull code, install dependencies, build frontend, and restart service."
fi

echo "==> 1. Prepare writable directories"
./scripts/prepare_writable_paths.sh

echo "==> 2. Prepare Python environment"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

if [ "$RUN_DEPLOY_STEPS" = "1" ]; then
  echo "==> 3. Install/update Python dependencies"
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt

  echo "==> 4. Build frontend"
  if command -v pnpm >/dev/null 2>&1; then
    (cd frontend && pnpm install --frozen-lockfile && pnpm build)
  else
    (cd frontend && npm install && npm run build)
  fi
else
  echo "==> 3. Skip dependency install"
  echo "==> 4. Skip frontend build"
fi

echo "==> 5. Run HK IPO data and daily report"
WAIT_SECONDS="$WAIT_SECONDS" ./scripts/run_all_data.sh "$REPORT_DATE"

if [ "$RUN_DEPLOY_STEPS" = "1" ]; then
  echo "==> 6. Restart service"
  systemctl restart "$SERVICE_NAME"
else
  echo "==> 6. Skip service restart"
fi

echo "==> 7. Wait for API"
if [ "$RUN_DEPLOY_STEPS" = "1" ]; then
  sleep 3
fi
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

echo "==> Finished at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "==> Data job complete"
