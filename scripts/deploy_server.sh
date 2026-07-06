#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/stock}"
SERVICE_NAME="${SERVICE_NAME:-stock-api}"
BRANCH="${BRANCH:-main}"

cd "$APP_DIR"

git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

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
