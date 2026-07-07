# Tencent Cloud data job

The data job script refreshes HK IPO data, generates the daily report, restarts the API, then refreshes A-share sentiment and US market data through the local API.

Install on the server:

```bash
cd /opt/stock
sudo cp deploy/systemd/stock-api.service /etc/systemd/system/
chmod +x scripts/tencent_data_job.sh
sudo cp deploy/systemd/stock-data-job.service /etc/systemd/system/
sudo cp deploy/systemd/stock-data-job.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stock-api.service
sudo systemctl enable --now stock-data-job.timer
```

Check the API:

```bash
curl -fsS http://127.0.0.1:8080/api/health
systemctl status stock-api.service --no-pager
```

Check schedule and logs:

```bash
systemctl list-timers stock-data-job.timer
journalctl -u stock-data-job.service -n 200 --no-pager
```

Run once manually:

```bash
sudo /opt/stock/scripts/tencent_data_job.sh
```

Run a specific date:

```bash
sudo /opt/stock/scripts/tencent_data_job.sh 2026-07-06
```

If the server timezone is not Asia/Shanghai, set it before enabling the timer:

```bash
sudo timedatectl set-timezone Asia/Shanghai
```
