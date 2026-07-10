# Nginx deployment

Use this Nginx config to serve the React build from `/opt/stock/frontend/dist` and reverse proxy `/api/` to the FastAPI service on `127.0.0.1:8080`.
HTTP is served directly instead of being forced to HTTPS, so the site remains reachable if the cloud provider blocks HTTPS/SNI before domain备案 is complete.

Install:

```bash
sudo cp deploy/nginx/stock.conf /etc/nginx/sites-available/stock.conf
sudo ln -sf /etc/nginx/sites-available/stock.conf /etc/nginx/sites-enabled/stock.conf
sudo nginx -t
sudo systemctl reload nginx
```

The config assumes Certbot certificates live at `/etc/letsencrypt/live/stockfenxi.cn/`. If the server uses a different certificate directory, update `ssl_certificate` and `ssl_certificate_key` before reloading Nginx.

Deploy the latest code and frontend build from your local machine. This is the
recommended path for mainland China servers because it does not require the
server to clone from GitHub:

```bash
REMOTE=ubuntu@www.stockfenxi.cn scripts/deploy_rsync.sh
```

If GitHub access from the server is reliable, you can also deploy from an
existing checkout on the server:

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
