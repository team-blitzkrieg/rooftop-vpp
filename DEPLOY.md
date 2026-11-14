# Deploy on one Ubuntu VM

The service reads meters and writes forecasts. It does not command an inverter. There is no setpoint route.

The stack is TimescaleDB, MLflow, a FastAPI process, and a worker. Caddy terminates HTTPS. Local `docker compose up` is the same stack without Caddy, with simulated June 2024 readings so you can hit the API before a meter exists.

Put the VM in a region near Sri Lanka. AWS Mumbai (`ap-south-1`) and DigitalOcean Bangalore are the straightforward choices. A 2 vCPU / 4 GB machine is enough for the pilot.

## Local

From the repository root, with Docker running:

```bash
docker compose up --build
```

The first boot trains two small models and writes a 24-hour forecast. That takes a few minutes. Then:

```bash
curl -s -H 'X-API-Key: local-dev-key' \
  'http://localhost:8000/forecast/home-dehiwala?target=pv'
```

`target` is `pv`, `demand`, or `net`. `net` is demand minus PV for the same hours. The body includes `issued_at`, `model_version`, `stale`, and `controls_equipment: false`. The seeded issue is 28 June 2024, so `stale` is true when you call it today. `data_label` is `SIMULATED`.

Device ingest for the seeded Dehiwala meter:

```bash
curl -s -X POST http://localhost:8000/ingest \
  -H 'X-Device-Token: local-device-key-home-dehiwala' \
  -H 'Content-Type: application/json' \
  -d '{"timestamp":"2024-06-28T12:00:00+05:30","pv_kw":1.2,"consumption_kw":0.4}'
```

Nugegoda and Moratuwa use `local-device-key-home-nugegoda` and `local-device-key-home-moratuwa`. Each device has its own token. The database stores the SHA-256 hash, not the token.

On-demand jobs, using the admin key:

```bash
curl -s -X POST http://localhost:8000/jobs/forecast -H 'X-Admin-Key: local-admin-key'
```

`/jobs/retrain` is the same shape. The worker also runs the forecast at minute 05 of every hour, Asia/Colombo, and the retrain on Sunday 18:30 UTC (Monday 00:00 in Colombo). A failed run inserts a failed row and leaves the previous forecast in place. The next read sets `using_previous`.

MLflow is on port 5000 inside the compose network (`http://localhost:5000` from the laptop). Do not leave 5000 or 5432 open on the VM.

The demand model in this service is trained from `consumption_kw`. The seed fills that column with a labelled schedule (morning and evening peaks). The household-demand research model is a separate change. When that model is registered under the name `demand` with the same features, the worker will load it. Until then, this registry model is what the API serves.

MQTT is off unless `MQTT_URL` is set. The stub subscribes to `rooftop/reading` and posts the same fields as `/ingest`, including `device_token`. It never publishes a command.

## VM

Ubuntu 24.04. Open only 22, 80, and 443.

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER"
git clone https://github.com/team-blitzkrieg/rooftop-vpp.git
cd rooftop-vpp
cp .env.example .env
```

Edit `.env`. Set `API_KEY`, `ADMIN_API_KEY`, and `DEVICE_TOKEN` to long random strings. Set `SITE_ADDRESS` to the hostname that points at the VM, and `CORS_ORIGINS` to the dashboard origin. Change the Postgres password in `.env` and in `docker-compose.yml` together if you do not want the example password on a public host.

```bash
docker compose --profile vm up -d --build
```

Caddy reads `Caddyfile` and asks Let's Encrypt for a certificate for `SITE_ADDRESS`. The name must resolve to this machine before you start Caddy. The API is then `https://SITE_ADDRESS`. Health is `GET /health` and does not need the API key.

The front end sends `X-API-Key` or `Authorization: Bearer <API_KEY>`. Forecast updates are server-sent events:

```text
GET /forecast/{site_id}/events?target=pv
```

`stale` is true when `issued_at` is older than `STALE_AFTER_MINUTES` (120 by default, a bit more than one missed hourly run).

### Artefacts

MLflow tracking uses the `mlflow` database. Model files sit on the `mlflow-data` volume (`file:///mlflow`). To use S3 or another S3-compatible store instead, set `MLFLOW_S3_ENDPOINT_URL`, the access key, and the secret, and change the MLflow command's `--default-artifact-root` to `s3://<bucket>/mlflow`. The registry alias `production` is what the worker loads.

A weekly retrain registers a new version. The alias moves only when the new holdout MAE is lower than the baseline and lower than the current Production model. The first seed promotes an initial model so the API has something to serve, and it logs the holdout comparison.

### Backups

```bash
sudo mkdir -p /var/backups/rooftop
sudo crontab -e
```

```cron
15 20 * * * BACKUP_DIR=/var/backups/rooftop /opt/rooftop-vpp/deploy/backup.sh >> /var/log/rooftop-backup.log 2>&1
```

20:15 UTC is after the Colombo evening. The script keeps 14 days of `pg_dump` files for the `rooftop` and `mlflow` databases. Copy them off the VM. Restoring is `gunzip -c file.sql.gz | docker compose exec -T db psql -U rooftop -d rooftop`.

### Updates

```bash
git pull
docker compose --profile vm up -d --build
```

Postgres data stays in the `db-data` volume. Migrations in `migrations/` run when the API, the worker, and the seed start. A migration that has already been applied is skipped.

## Tests

```bash
pip install -r requirements-serve.txt
python -m pytest tests/test_serve.py
```

Those tests use an in-memory store and a temporary MLflow sqlite file. They do not call Open-Meteo. The hourly job on the VM does call Open-Meteo. If that call fails, the last good forecast stays.
