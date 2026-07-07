#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/stock}"
SERVICE_NAME="${SERVICE_NAME:-stock-api}"
PORT="${PORT:-8080}"
DOMAIN="${DOMAIN:-equity-research-hong-kong-stocks.cn}"
WWW_DOMAIN="${WWW_DOMAIN:-www.${DOMAIN}}"
NGINX_SITE="${NGINX_SITE:-stock.conf}"
FRONTEND_DIR="${FRONTEND_DIR:-${APP_DIR}/frontend/dist}"
CERT_DIR="${CERT_DIR:-/etc/letsencrypt/live/${DOMAIN}}"

if [ "$(id -u)" = "0" ]; then
  SUDO=""
else
  SUDO="sudo"
fi

disable_duplicate_nginx_sites() {
  local target_available target_enabled resolved_target file resolved_file
  target_available="/etc/nginx/sites-available/${NGINX_SITE}"
  target_enabled="/etc/nginx/sites-enabled/${NGINX_SITE}"
  resolved_target="$(readlink -f "$target_available" 2>/dev/null || true)"

  echo "==> Disable duplicate nginx sites for ${DOMAIN}"
  while IFS= read -r file; do
    [ -n "$file" ] || continue
    resolved_file="$(readlink -f "$file" 2>/dev/null || true)"
    if [ "$file" = "$target_enabled" ] || { [ -n "$resolved_file" ] && [ "$resolved_file" = "$resolved_target" ]; }; then
      continue
    fi
    echo "Disabling duplicate nginx config: ${file}"
    $SUDO rm -f "$file"
  done < <(grep -RslE "server_name .*(${DOMAIN}|${WWW_DOMAIN})" /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null || true)
}

echo "==> App dir: ${APP_DIR}"
echo "==> Domain: ${DOMAIN} ${WWW_DOMAIN}"

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: APP_DIR not found: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

echo "==> 1. Ensure frontend build exists"
if [ ! -d "$FRONTEND_DIR" ] || [ ! -f "$FRONTEND_DIR/index.html" ]; then
  if command -v pnpm >/dev/null 2>&1; then
    (cd frontend && pnpm install --frozen-lockfile && pnpm build)
  else
    (cd frontend && npm install && npm run build)
  fi
fi

echo "==> 2. Restart API service"
$SUDO systemctl restart "$SERVICE_NAME"
sleep 2
curl --connect-timeout 5 --max-time 15 -fsS "http://127.0.0.1:${PORT}/api/health"
echo

echo "==> 3. Install nginx site"
$SUDO mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled

if [ -f "${CERT_DIR}/fullchain.pem" ] && [ -f "${CERT_DIR}/privkey.pem" ]; then
  echo "Found certificate in ${CERT_DIR}; installing HTTP + HTTPS config."
  $SUDO tee "/etc/nginx/sites-available/${NGINX_SITE}" >/dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN} ${WWW_DOMAIN};

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name ${DOMAIN} ${WWW_DOMAIN};

    ssl_certificate ${CERT_DIR}/fullchain.pem;
    ssl_certificate_key ${CERT_DIR}/privkey.pem;
    ssl_protocols TLSv1.2;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    root ${FRONTEND_DIR};
    index index.html;

    client_max_body_size 20m;

    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_vary on;
    gzip_types application/javascript application/json application/xml image/svg+xml text/css text/javascript text/plain text/xml;

    location = /api/health {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 15s;
        proxy_connect_timeout 5s;
    }

    location ^~ /api/ {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 10s;
        proxy_send_timeout 180s;
        proxy_read_timeout 180s;
        add_header Cache-Control "no-store" always;
    }

    location ^~ /assets/ {
        try_files \$uri =404;
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
    }

    location = /index.html {
        add_header Cache-Control "no-cache" always;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
        add_header Cache-Control "no-cache" always;
    }
}
EOF
else
  echo "Certificate not found in ${CERT_DIR}; installing HTTP-only recovery config."
  $SUDO tee "/etc/nginx/sites-available/${NGINX_SITE}" >/dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN} ${WWW_DOMAIN};

    root ${FRONTEND_DIR};
    index index.html;

    client_max_body_size 20m;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location = /api/health {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 15s;
        proxy_connect_timeout 5s;
    }

    location ^~ /api/ {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 10s;
        proxy_send_timeout 180s;
        proxy_read_timeout 180s;
        add_header Cache-Control "no-store" always;
    }

    location ^~ /assets/ {
        try_files \$uri =404;
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
    }

    location = /index.html {
        add_header Cache-Control "no-cache" always;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
        add_header Cache-Control "no-cache" always;
    }
}
EOF
fi

$SUDO ln -sf "/etc/nginx/sites-available/${NGINX_SITE}" "/etc/nginx/sites-enabled/${NGINX_SITE}"
if [ -e /etc/nginx/sites-enabled/default ]; then
  $SUDO rm -f /etc/nginx/sites-enabled/default
fi
disable_duplicate_nginx_sites

echo "==> 4. Test and restart nginx"
$SUDO nginx -t
$SUDO systemctl restart nginx

echo "==> 5. Verify local nginx"
curl --connect-timeout 5 --max-time 15 -I -H "Host: ${WWW_DOMAIN}" "http://127.0.0.1/" || true
curl --connect-timeout 5 --max-time 15 -fsS -H "Host: ${WWW_DOMAIN}" "http://127.0.0.1/api/health" || true
echo

echo "==> 6. Listening ports"
$SUDO ss -lntp | grep -E ':80|:443|:'"${PORT}" || true

echo "==> Domain repair complete"
echo "Test externally:"
echo "  http://${WWW_DOMAIN}/"
echo "  https://${WWW_DOMAIN}/"
