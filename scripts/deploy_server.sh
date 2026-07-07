#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/stock}"
SERVICE_NAME="${SERVICE_NAME:-stock-api}"
BRANCH="${BRANCH:-main}"
APP_USER="${APP_USER:-}"

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

git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
if [ "$(id -u)" = "0" ]; then
  git config --system --add safe.directory "$APP_DIR" 2>/dev/null || true
fi

cd "$APP_DIR"

git fetch origin "$BRANCH"

STASH_CREATED=0
if [ -n "$(git status --porcelain)" ]; then
  echo "Local changes detected; stashing before updating ${BRANCH}."
  git stash push --include-untracked -m "deploy-autostash $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  STASH_CREATED=1
fi

git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [ "$STASH_CREATED" = "1" ]; then
  echo "Previous local changes were preserved in git stash."
fi

echo "Preparing writable generated-file paths."
mkdir -p data prospectuses output
if [ "$(id -u)" = "0" ]; then
  APP_USER="${APP_USER:-$(service_user)}"
  chown -R "$APP_USER":"$APP_USER" data prospectuses output 2>/dev/null || true
  chown "$APP_USER":"$APP_USER" ipo_daily_analysis.html ipo_daily_analysis.md ipo_daily_analysis.pdf 2>/dev/null || true
fi
chmod -R a+rwX data prospectuses output
chmod a+rw ipo_daily_analysis.html ipo_daily_analysis.md ipo_daily_analysis.pdf 2>/dev/null || true

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

curl -fsS "http://127.0.0.1:8080/api/health"
echo
