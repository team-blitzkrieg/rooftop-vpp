# Dashboard

Owner: Senesh Fernando (software).

## PV forecast browser (Streamlit)

Browse LightGBM rooftop PV model outputs for the Sri Lanka pilot: test MAE vs the physics
baseline, per-day forecast curves (Colombo issue time), and the training experiment report.

Artifacts are read from paths **relative to the repository root** (same layout as
`forecasting.config.REPO_ROOT`):

| Path | Contents |
|------|----------|
| `forecasting/models/pv-lgbm-<timestamp>/` | `experiment.json`, `experiment.md`, `model.txt` |
| `data/processed/forecasts/pv-lgbm-<timestamp>/<site_id>/<YYYY-MM-DD>.csv` | 24 h forecast rows |
| `forecasting/sites.example.csv` | Pilot site names and metadata |

### Static site (GitHub Pages)

Streamlit cannot run on `github.io` (static hosting only). The same metrics and forecast curves are published as a static site:

**https://team-blitzkrieg.github.io/rooftop-vpp/**

Source lives under `docs/` in the repo root. Regenerate `docs/data/` with `python scripts/export_github_pages.py` (add `--with-demo-train` for a short synthetic model). See the root README **GitHub Pages** section.

### Deploy on Vercel

The static PV forecast page is Vercel-ready via root `vercel.json` (`outputDirectory`: `docs`, no cloud build). Connect the GitHub repo at [vercel.com](https://vercel.com), root directory `.`, framework **Other/None**. Private repos work on Vercel Hobby. After connect, pushes deploy to `https://<project-name>.vercel.app`.

Refresh `docs/data` locally (see export command above), commit, and push — same workflow as GitHub Pages. Optionally enable a Vercel build command to run the export script on deploy only if you accept Python/LightGBM on the builder; see root README **Deploy on Vercel**.

### Run locally

From the **repo root**, with the project virtual environment activated and dependencies installed:

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8493
```

Open http://127.0.0.1:8493. Page title: **Rooftop VPP Forecast**.

If no model directory exists yet, the Overview tab explains how to train. Example short synthetic run:

```bash
python -m forecasting train --synthetic --start 2024-06-01 --end 2024-06-21 --estimators 80
```

The UI can trigger the same command from a button; it does **not** train on import.

### Files

- `app.py` — Streamlit tabs: Overview, Forecast day, Model report
- `artifacts.py` — list models, load experiment JSON, read forecast CSVs

### Planned later

- Household schedule and savings view
- Utility VPP view (aggregated exports, battery state, transformer loading)