#!/usr/bin/env bash
set -u

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SERVICE_NAME="${SERVICE_NAME:-stock-api}"
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

cd "$APP_DIR" || exit 1

mkdir -p data prospectuses output || exit 1

for path in ipo_daily_analysis.html ipo_daily_analysis.md ipo_daily_analysis.pdf; do
  if [ ! -e "$path" ]; then
    : >"$path" 2>/dev/null || true
  fi
done

if [ "$(id -u)" = "0" ]; then
  APP_USER="${APP_USER:-$(service_user)}"
  echo "Preparing writable generated-file paths for ${APP_USER}."
  chown -R "$APP_USER":"$APP_USER" data prospectuses output 2>/dev/null || true
  chown "$APP_USER":"$APP_USER" \
    ipo_daily_analysis.html \
    ipo_daily_analysis.md \
    ipo_daily_analysis.pdf 2>/dev/null || true
else
  echo "Preparing writable generated-file paths as $(id -un)."
fi

chmod -R a+rwX data prospectuses output 2>/dev/null || true
chmod a+rw \
  ipo_daily_analysis.html \
  ipo_daily_analysis.md \
  ipo_daily_analysis.pdf 2>/dev/null || true

for dir in data prospectuses output; do
  if [ ! -w "$dir" ]; then
    echo "ERROR: ${APP_DIR}/${dir} is not writable by $(id -un). Run: sudo APP_DIR=${APP_DIR} SERVICE_NAME=${SERVICE_NAME} scripts/prepare_writable_paths.sh" >&2
    exit 13
  fi
done

for path in ipo_daily_analysis.html ipo_daily_analysis.md ipo_daily_analysis.pdf; do
  if [ -e "$path" ] && [ ! -w "$path" ]; then
    echo "ERROR: ${APP_DIR}/${path} is not writable by $(id -un). Run: sudo APP_DIR=${APP_DIR} SERVICE_NAME=${SERVICE_NAME} scripts/prepare_writable_paths.sh" >&2
    exit 13
  fi
done
