#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/stock}"
SERVICE_NAME="${SERVICE_NAME:-stock-api}"
BRANCH="${BRANCH:-main}"
APP_USER="${APP_USER:-}"
PORT="${PORT:-8080}"
GIT_TIMEOUT="${GIT_TIMEOUT:-180}"
DEPLOY_LOCK="${DEPLOY_LOCK:-/var/lock/${SERVICE_NAME}-deploy.lock}"

if command -v flock >/dev/null 2>&1; then
  exec 9>"$DEPLOY_LOCK"
  if ! flock -n 9; then
    echo "Another deploy is already running: $DEPLOY_LOCK" >&2
    exit 1
  fi
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
  sudo systemctl status "$SERVICE_NAME" --no-pager -l >&2 || true
  return 1
}

git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
if [ "$(id -u)" = "0" ]; then
  git config --system --add safe.directory "$APP_DIR" 2>/dev/null || true
fi

cd "$APP_DIR"

echo "==> Fetch ${BRANCH} from origin with ${GIT_TIMEOUT}s timeout"
if ! GIT_TERMINAL_PROMPT=0 timeout "$GIT_TIMEOUT" git fetch origin "$BRANCH"; then
  cat >&2 <<EOF
ERROR: git fetch timed out or failed.

This server may not be able to reach GitHub reliably. For mainland China
servers, prefer the local rsync deploy:

  REMOTE=ubuntu@www.stockfenxi.cn scripts/deploy_rsync.sh
EOF
  exit 1
fi

STASH_CREATED=0
if [ -n "$(git status --porcelain)" ]; then
  echo "Local changes detected; stashing before updating ${BRANCH}."
  git stash push --include-untracked -m "deploy-autostash $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  STASH_CREATED=1
fi

git checkout "$BRANCH"
echo "==> Pull ${BRANCH} with ${GIT_TIMEOUT}s timeout"
if ! GIT_TERMINAL_PROMPT=0 timeout "$GIT_TIMEOUT" git pull --ff-only origin "$BRANCH"; then
  echo "ERROR: git pull timed out or failed." >&2
  exit 1
fi

if [ "$STASH_CREATED" = "1" ]; then
  echo "Previous local changes were preserved in git stash."
fi

./scripts/prepare_writable_paths.sh

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if command -v pnpm >/dev/null 2>&1; then
  (cd frontend && pnpm install --frozen-lockfile && pnpm build)
else
  (cd frontend && npm install && npm run build)
fi

sudo systemctl restart "$SERVICE_NAME"
sudo nginx -t
sudo systemctl reload nginx

wait_for_health
