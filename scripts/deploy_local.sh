#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/stock}"
SERVICE_NAME="${SERVICE_NAME:-stock-api}"
PORT="${PORT:-8080}"
DEPLOY_LOCK="${DEPLOY_LOCK:-/tmp/${SERVICE_NAME}-local-deploy.lock}"

if command -v flock >/dev/null 2>&1; then
  exec 9>"$DEPLOY_LOCK"
  if ! flock -n 9; then
    echo "Another deploy is already running: $DEPLOY_LOCK" >&2
    exit 1
  fi
fi

wait_for_health() {
  local url="http://127.0.0.1:${PORT}/api/health"
  local attempt
  for attempt in $(seq 1 20); do
    if curl --connect-timeout 2 --max-time 5 -fsS "$url" 2>/dev/null; then
      echo
      return 0
    fi
    sleep 1
  done
  echo "ERROR: health check failed after restart: $url" >&2
  systemctl status "$SERVICE_NAME" --no-pager -l >&2 || true
  return 1
}

echo "==> Local deploy stock app"
echo "APP_DIR=${APP_DIR}"
echo "SERVICE_NAME=${SERVICE_NAME}"
echo "PORT=${PORT}"

cd "$APP_DIR"

echo "==> 1. Prepare writable paths"
./scripts/prepare_writable_paths.sh

echo "==> 2. Install Python dependencies"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "==> 3. Build frontend"
if command -v pnpm >/dev/null 2>&1; then
  (cd frontend && pnpm install --frozen-lockfile && pnpm build)
elif command -v corepack >/dev/null 2>&1; then
  corepack enable
  (cd frontend && corepack pnpm install --frozen-lockfile && corepack pnpm build)
else
  (cd frontend && npm install && npm run build)
fi

echo "==> 4. Restart services"
cp deploy/systemd/stock-api.service /etc/systemd/system/stock-api.service
systemctl daemon-reload
systemctl restart "$SERVICE_NAME"
nginx -t
systemctl reload nginx

echo "==> 5. Health check"
wait_for_health

echo "==> Local deploy complete"
