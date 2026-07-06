# Nginx deployment

Use this Nginx config to serve the React build from `/opt/stock/frontend/dist` and reverse proxy `/api/` to the FastAPI service on `127.0.0.1:8080`.

Install:

```bash
sudo cp deploy/nginx/stock.conf /etc/nginx/sites-available/stock.conf
sudo ln -sf /etc/nginx/sites-available/stock.conf /etc/nginx/sites-enabled/stock.conf
sudo nginx -t
sudo systemctl reload nginx
```

The config assumes Certbot certificates live at `/etc/letsencrypt/live/equity-research-hong-kong-stocks.cn/`. If the server uses a different certificate directory, update `ssl_certificate` and `ssl_certificate_key` before reloading Nginx.

Deploy the latest code and frontend build:

```bash
chmod +x scripts/deploy_server.sh
sudo APP_DIR=/opt/stock SERVICE_NAME=stock-api BRANCH=main scripts/deploy_server.sh
```

For mainland China access, put the domain behind a CDN or EdgeOne acceleration rule:

- Origin: `43.132.228.61`
- HTTPS origin protocol: HTTPS
- Cache `/assets/*`: 30 days or longer
- Do not cache `/api/*`
- Do not cache `/index.html`
- Enable gzip/Brotli
