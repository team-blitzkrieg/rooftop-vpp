# Deploy on free tiers

The pilot reads forecasts. Nothing in this deploy writes a setpoint or opens a serial port.

Three free pieces:

- Supabase free Postgres holds sites, meter readings, forecasts and the model metadata table.
- GitHub Actions runs the hourly forecast and the weekly retrain.
- Render free web service, or a Hugging Face Space, serves the FastAPI app.

Vercel is not used for the backend. The API is the Render service or the Hugging Face Space above. `vercel.json` sets `ignoreCommand` to `exit 0`, so Vercel skips the build instead of bundling this Python repo into a serverless function.

`docker compose` is only for a laptop. It starts Postgres 16 and the API. It is not the hosted setup.

```bash
docker compose up --build
```

The API is then on `http://localhost:8000`. Docs are at `/docs`. `GET /health` returns `controls_equipment: false`.

## Limits worth knowing

These are the free-plan caps as published around 2026. Check the vendor page before you rely on a number, because they change them.

Supabase free:

- Database about 500 MB. File storage about 1 GB. Both are shared by the whole project.
- The project pauses after about a week with no queries. The hourly job is the activity that keeps it awake. If it still pauses, restore it from the Supabase dashboard. Forecasts already stored are still there.
- Direct connections are limited (on the order of 60, and the pooler is the one to use from Actions and Render). Use the pooler connection string as `DATABASE_URL`.
- Egress is capped. The front end should poll once an hour, not stream.

GitHub Actions:

- A public repository gets unlimited minutes on the standard runner. A private repository gets 2,000 minutes a month.
- Scheduled workflows can start late. GitHub may also disable the schedule after 60 days with no commit. A push turns it back on.
- The hourly job is about 24 times a day. Keep it short. Do not upload the model from that job.

Render free web service:

- Sleeps after about 15 minutes with no traffic. The next request cold-starts. That is acceptable, because the front end polls hourly.
- 750 instance hours a month. One service that is woken once an hour and then sleeps stays inside that. Do not add a second always-on service.
- No disk you can keep. Models live in Supabase Storage or a GitHub Release, not on the instance.

Hugging Face Spaces (Docker, free CPU):

- Sleeps when idle, same idea as Render. Set the Space port to 7860. The image reads `PORT`, and Spaces sets that to 7860.
- Storage on the Space is small and ephemeral. Do not put the model registry there.

How to stay inside those caps:

- Keep readings for 90 days and forecast rows for 30 days. The weekly job deletes the rest, and it leaves the latest successful forecast in place.
- Store one model zip per retrain, not one per hour. Promote it only when its test MAE is lower than the model already marked promoted.
- Hourly resolution is enough for the pilot. A 15-minute series fills the 500 MB faster.
- The front end polls `GET /forecasts/{site_id}` once an hour. No WebSocket.
- If the API is asleep, read `forecasts` and `model_versions` from Supabase with the anon key. Those tables allow select. `readings` and `devices` do not.

## 1. Supabase

Create a free project. In the SQL editor, paste `api/schema.sql` and run it.

The script creates ordinary tables and indexes on `(site_id, timestamp)`. If the Timescale extension is installed, it also tries to turn `readings` and `forecasts` into hypertables. On a normal free project that extension is not there, and the script carries on with plain Postgres.

Row level security is on for every table. `anon` may select `forecasts`, `model_versions` and `sites`. It may not select `readings` or `devices`, and it has no insert policy on `readings`.

Copy the pooler URI into the GitHub secret `DATABASE_URL`. Use the transaction pooler (port 6543). Direct connections are too few for Actions. PgBouncer in transaction mode rejects named prepared statements (`prepared statement "_pg3_0" already exists`). `PostgresStore` opens every psycopg connection with `prepare_threshold=None`, which is what the hourly forecast, the weekly retrain, and Seed demo use. Copy the project URL into `SUPABASE_URL`. Copy the service role key into `SUPABASE_SERVICE_ROLE_KEY`. The service role bypasses RLS. It is not the anon key, and it does not belong in the front end.

In Storage, you can leave the bucket absent. The weekly job creates a private bucket named `models` when those two secrets are set.

Add a site and a device key. The key is stored as a SHA-256 hash, not as the raw string.

```sql
insert into sites (site_id, name, timezone, system_kw, latitude, longitude, has_meter, demand_scale_kw)
values ('home-dehiwala', 'Dehiwala', 'Asia/Colombo', 3.0, 6.85, 79.87, true, 1.2);

insert into devices (device_id, site_id, key_sha256)
values (
    'meter-dehiwala',
    'home-dehiwala',
    encode(digest('paste-a-long-random-key', 'sha256'), 'hex')
);
```

A meter can post to the API (`POST /ingest`, header `X-Device-Key`) or call the SQL function with the anon key:

```sql
select ingest_reading(
    'paste-a-long-random-key',
    '2024-06-01T19:00:00+05:30',
    null,   -- pv_kw
    0.80,   -- consumption_kw
    null,
    null
);
```

Unknown keys raise `unknown device key` and write nothing.

## 2. GitHub Actions

Repository secrets, Settings → Secrets and variables → Actions:

| Secret | Used for |
| --- | --- |
| `DATABASE_URL` | Supabase pooler URI |
| `SUPABASE_URL` | `https://<project>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Storage upload and server-side writes |
| `ADMIN_API_KEY` | Only if something calls `POST /models` |
| `READ_API_KEY` | Optional. Empty means forecast reads are open |
| `DEMO_DEVICE_KEY` | Raw token for the demo Pi on site `demo-sim`. Never commit it. |

`GITHUB_TOKEN` is provided by Actions. You do not paste it.

Workflows:

- `.github/workflows/forecast.yml` at minute 15 of every hour. If `DATABASE_URL` is empty it prints a line and exits 0, so a fork without secrets stays green.
- `.github/workflows/retrain.yml` on Sunday 18:30 UTC, which is Monday 00:00 in Asia/Colombo. It trains on rows with `is_simulated = false`. Fewer than three issue days, and it keeps the promoted model. A worse test MAE is saved and not promoted.

The weekly workflow has a manual input, `allow_synthetic`. Leave it false. Turning it on trains on generated rows and can replace the production model. The cron does not set it.

`.github/workflows/demo-pi.yml` runs every 30 minutes and on demand. It posts SIMULATED readings for site `demo-sim` to the ingest URL. If `DEMO_DEVICE_KEY` is missing it prints a skip line and exits green. The manual input `backfill_days` seeds past days (0 posts only the latest slots). See `docs/edge-ingest.md`.

`.github/workflows/seed-demo.yml` is manual only (`workflow_dispatch`, no cron). Actions → Seed demo → Run workflow. It inserts Dehiwala, Nugegoda and Moratuwa into `sites` when those ids are missing, trains PV and demand on the synthetic generator, and writes the next 48 hourly rows for `pv`, `demand` and `net`. Every row has `data_label` `SIMULATED`, `is_simulated` true, and `model_version` `demo`. It does not insert meter readings and it never sets `promoted` on `model_versions`, so the hourly job and the weekly retrain are unchanged. Running it again replaces the previous demo rows.

The page in `web/` reads `sites` and `forecasts` in the browser. It is a separate Vercel project with Root Directory `web`. The repository-root `vercel.json` still skips builds for a project rooted at the repo, which is what keeps the Python tree off Vercel. See `web/README.md`.

The retrain uploads one zip, either to the private Supabase bucket or, if those secrets are empty, as a GitHub Release asset tagged `model-<version>`. The `model_versions` row stores the URL, the metrics and `promoted`. If the upload fails, the row is still written. Local MLflow is not part of this. Anyone who wants it on a laptop can point the MLflow CLI at `forecasting/models`. There is no MLflow server to pay for.

## 3. Render or Hugging Face

Render: New → Web Service → this repo → Docker. Free instance. Environment variables are the same names as the secrets above, plus `PORT` if you want one (Render sets it). Health check path `/health`.

Hugging Face: New Space → Docker. Put the same variables in the Space secrets. The container listens on `$PORT`.

Cold start is normal. The page can fall back to Supabase:

```javascript
const { data } = await supabase
  .from("forecasts")
  .select("timestamp,value_kw,baseline_kw,net_kw,issued_at,data_label,model_version")
  .eq("site_id", "home-dehiwala")
  .eq("target", "demand")
  .order("issued_at", { ascending: false })
  .limit(24);
```

Use the anon key in the browser. Do not ship the service role key.

`issued_at` older than 26 hours is stale. The API sets `stale` and, when a newer run failed, `using_previous`. The fallback query should do the same check in the page. A failed run does not delete the previous successful rows.

`controls_equipment` is false on every response. There is no route that writes a setpoint.

## Local checks

```bash
pip install -r requirements.txt
python -m pytest
python -m api.jobs forecast
```

The last command exits 0 without `DATABASE_URL`. With the compose database it will look for a promoted model, find none, and refresh the labelled simulated forecast instead of leaving the previous issue in place. A promoted model is left alone.

## Household tables and the Pi

`api/migrations/2026-11-17-household.sql` adds profiles, consent, loads, pauses, seen alerts, coordinator assignments, cases, fault results, and the ingest rate-limit table. Paste it in the Supabase SQL editor. Row level security lets a signed-in user read and write their own rows. `anon` can read `fault_results`. It still cannot read `readings` or `devices`.

The Pi posts to `POST /api/ingest` on the Vercel app. The contract is `docs/edge-ingest.md`. Set `SUPABASE_SERVICE_ROLE_KEY` on the `rooftop-web` Vercel project only. Do not prefix it with `NEXT_PUBLIC_`.

The household screen reads `demo-sim` readings through that same server key and labels them SIMULATED. The browser key still cannot read `readings` for any other site.

Email sign-in uses Supabase Auth (magic code). Demo sign-in stays in the browser and is labelled as a demo. In Authentication → Providers, email must stay enabled. The free project already includes that.

The hourly forecast workflow connects with `DATABASE_URL`. If that secret is a URI with a stray parenthesis (a note copied from the dashboard), the job fails before it can write. The value has to be the pooler URI alone. When no model is promoted, the job refreshes the simulated forecast so `issued_at` moves. GitHub may still start the cron late; that delay is on GitHub's side.
