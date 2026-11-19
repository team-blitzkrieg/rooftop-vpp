# Edge ingest contract

Mithil's Pi posts meter readings here. The app never sends a command back. A successful response does not change an inverter.

## Endpoint

`POST https://<rooftop-web>/api/ingest`

The household app on Vercel serves this. It is not the Python process.

## Auth

Send the per-site device token in either header:

- `X-Device-Key: <token>`
- `Authorization: Bearer <token>`

The database stores only `sha256(token)` in `devices.key_sha256`. A wrong token gets `401` and writes nothing. Do not put the token in the JSON body or in a log.

Senesh creates the row in the Supabase SQL editor:

```sql
insert into devices (device_id, site_id, key_sha256)
values (
  'meter-dehiwala',
  'home-dehiwala',
  encode(digest('paste-a-long-random-key', 'sha256'), 'hex')
);
```

The Pi keeps the raw token. The repo never does.

## Body

One reading, or a batch. Times are ISO-8601. Powers are kW, zero or positive, and may be null. At least one power field is required. At most 48 readings per request.

```json
{
  "readings": [
    {
      "timestamp": "2026-11-17T10:00:00+05:30",
      "pv_kw": 1.2,
      "consumption_kw": 0.4,
      "import_kw": 0.0,
      "export_kw": 0.8,
      "data_label": "MEASURED",
      "is_simulated": false
    }
  ]
}
```

`data_label` is `MEASURED`, `ESTIMATED`, or `SIMULATED`. Omit it and a real reading is `MEASURED`. A simulated reading must set both `is_simulated: true` and `data_label: "SIMULATED"`.

The same `site_id` and `timestamp` is an upsert. Sending the hour again replaces that hour. It does not create a second row.

## Responses

| Status | Meaning |
| --- | --- |
| 200 | `{ "site_id", "upserted", "data_label", "controls_equipment": false }` |
| 401 | Missing or unknown device token |
| 422 | Bad JSON or a failed check |
| 429 | More than 30 requests from this site in the last minute |
| 503 | Server secret or the new tables are not in place yet |

`controls_equipment` is always false.

## What Senesh turns on

1. Run `api/migrations/2026-11-17-household.sql` in the Supabase SQL editor (or paste all of `api/schema.sql` on a new project).
2. On the Vercel project `rooftop-web`, set `SUPABASE_SERVICE_ROLE_KEY` for Production and Preview. Do not mark it `NEXT_PUBLIC_`. The browser must not receive it.
3. Insert the device row above, and give Mithil the raw token out of band.

## Demo Pi simulator

Until the real Pi is posting, `edge/sim/demo_pi.py` pretends to be the device `demo-sim-pi` on site `demo-sim` (Demo home (SIMULATED), 3 kW, Colombo). It does not command an inverter.

Each slot uses a fixed seed from the Colombo date plus the slot index, so a rerun produces the same kW and the upsert replaces that timestamp. PV is pvlib clear-sky irradiance scaled to 3 kW with seeded cloud noise. Household use has a morning peak near 07:00 and an evening peak near 19:30, scaled by `demand_scale_kw` 1.2. Import and export come from those two. Every reading sets `is_simulated: true` and `data_label: "SIMULATED"`.

The default resolution is 15 minutes. `--resolution hourly` is the other choice. A request never carries more than 48 readings.

It POSTs to `INGEST_URL`, which defaults to `https://rooftop-web-gamma.vercel.app/api/ingest`, with the raw token in `X-Device-Key` from the environment variable `DEMO_DEVICE_KEY`. The script prints slot counts and HTTP status codes. It does not print the token.

```bash
DEMO_DEVICE_KEY='the-raw-token' python -m edge.sim.demo_pi --backfill-days 2
python -m edge.sim.demo_pi --dry-run
```

`--backfill-days` defaults to 0. That posts the last three hours of slots, so a late run still covers the recent ones. Set it from 1 to 14 to seed past midnights as well. `--dry-run` prints counts and does not POST. If `DEMO_DEVICE_KEY` is empty, the script says so and posts nothing.

`.github/workflows/demo-pi.yml` runs that command every 30 minutes, and on demand with a `backfill_days` input. The site and device rows are already in Supabase. Senesh adds the repository secret `DEMO_DEVICE_KEY` whose sha256 matches `devices.key_sha256` for `demo-sim-pi`. If that secret is missing, the job prints the skip line and stays green. An optional Actions variable `INGEST_URL` overrides the default host.

The household app loads these readings only for `demo-sim`, through the server, and shows them with a SIMULATED label. Other meters stay unreadable to the browser key.
