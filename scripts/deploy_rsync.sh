#!/usr/bin/env bash
set -euo pipefail

REMOTE="${REMOTE:-ubuntu@www.stockfenxi.cn}"
APP_DIR="${APP_DIR:-/opt/stock}"
SERVICE_NAME="${SERVICE_NAME:-stock-api}"
PORT="${PORT:-8080}"
TMP_DIR="${TMP_DIR:-/tmp/stock-upload}"
SSH_OPTS="${SSH_OPTS:-}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: rsync is required on the local machine." >&2
  exit 1
fi

echo "==> Deploy stock app via rsync"
echo "REMOTE=${REMOTE}"
echo "APP_DIR=${APP_DIR}"
echo "SERVICE_NAME=${SERVICE_NAME}"
echo "PORT=${PORT}"

ssh ${SSH_OPTS} "$REMOTE" "command -v rsync >/dev/null && command -v sudo >/dev/null"

echo "==> 1. Upload source to ${REMOTE}:${TMP_DIR}"
ssh ${SSH_OPTS} "$REMOTE" "rm -rf '$TMP_DIR' && mkdir -p '$TMP_DIR'"
rsync -az --delete \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='.local-bin/' \
  --exclude='.pytest_cache/' \
  --exclude='.DS_Store' \
  --exclude='frontend/node_modules/' \
  --exclude='frontend/dist/' \
  --exclude='frontend/coverage/' \
  --exclude='frontend/*.tsbuildinfo' \
  --exclude='data/' \
  --exclude='output/' \
  --exclude='prospectuses/' \
  "$ROOT/" "$REMOTE:$TMP_DIR/"

echo "==> 2. Install source on server"
ssh ${SSH_OPTS} "$REMOTE" "APP_DIR='$APP_DIR' TMP_DIR='$TMP_DIR' bash -s" <<'REMOTE_INSTALL'
set -euo pipefail
sudo mkdir -p "$APP_DIR"
sudo rsync -a --delete \
  --exclude='.venv/' \
  --exclude='frontend/node_modules/' \
  --exclude='frontend/dist/' \
  --exclude='data/' \
  --exclude='output/' \
  --exclude='prospectuses/' \
  "$TMP_DIR/" "$APP_DIR/"
sudo mkdir -p "$APP_DIR/data" "$APP_DIR/output" "$APP_DIR/prospectuses"
sudo chmod +x "$APP_DIR"/scripts/*.sh "$APP_DIR/run.sh"
REMOTE_INSTALL

echo "==> 3. Build and restart on server"
ssh ${SSH_OPTS} "$REMOTE" "APP_DIR='$APP_DIR' SERVICE_NAME='$SERVICE_NAME' PORT='$PORT' bash -s" <<'REMOTE_DEPLOY'
set -euo pipefail
cd "$APP_DIR"

if command -v flock >/dev/null 2>&1; then
  exec 9>"/tmp/${SERVICE_NAME}-deploy.lock"
  if ! flock -n 9; then
    echo "Another deploy is already running." >&2
    exit 1
  fi
fi

sudo ./scripts/prepare_writable_paths.sh

if [ ! -d .venv ]; then
  sudo python3 -m venv .venv
fi
sudo .venv/bin/python -m pip install --upgrade pip
sudo .venv/bin/python -m pip install -r requirements.txt

if command -v pnpm >/dev/null 2>&1; then
  sudo sh -c 'cd frontend && pnpm install --frozen-lockfile && pnpm build'
elif command -v corepack >/dev/null 2>&1; then
  sudo corepack enable
  sudo sh -c 'cd frontend && corepack pnpm install --frozen-lockfile && corepack pnpm build'
else
  sudo sh -c 'cd frontend && npm install && npm run build'
fi

sudo cp deploy/systemd/stock-api.service /etc/systemd/system/stock-api.service
sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE_NAME"
sudo nginx -t
sudo systemctl reload nginx

url="http://127.0.0.1:${PORT}/api/health"
for attempt in $(seq 1 20); do
  if curl --connect-timeout 2 --max-time 5 -fsS "$url" 2>/dev/null; then
    echo
    exit 0
  fi
  sleep 1
done

echo "ERROR: health check failed after restart: $url" >&2
sudo systemctl status "$SERVICE_NAME" --no-pager -l >&2 || true
exit 1
REMOTE_DEPLOY

echo "==> Deploy complete"
