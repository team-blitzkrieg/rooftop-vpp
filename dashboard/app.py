"""Streamlit browser for rooftop PV LightGBM forecast outputs (Sri Lanka pilot)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import artifacts
from forecasting.config import MODEL_DIR, REPO_ROOT

TRAIN_CMD = [
    sys.executable,
    "-m",
    "forecasting",
    "train",
    "--synthetic",
    "--start",
    "2024-06-01",
    "--end",
    "2024-06-21",
    "--estimators",
    "80",
]

st.set_page_config(page_title="Rooftop VPP Forecast", layout="wide")

st.title("Rooftop VPP — PV forecast")
st.caption(
    "Sri Lanka rooftop solar pilot · issue time midnight Asia/Colombo · "
    "forecasts are for scheduling only, not inverter commands."
)


def _no_models_panel() -> None:
    st.warning("No trained LightGBM model found under `forecasting/models/`.")
    st.markdown(
        """
From the **repository root** with your virtual environment active, train a short synthetic run:

```bash
python -m forecasting train --synthetic --start 2024-06-01 --end 2024-06-21 --estimators 80
```

That writes `forecasting/models/pv-lgbm-<timestamp>/` and matching forecast CSVs under
`data/processed/forecasts/`. Refresh this page after training finishes.
"""
    )
    if st.button("Run short synthetic train (≈1–3 min)", type="primary"):
        with st.spinner("Training LightGBM on simulated Colombo-area rooftops…"):
            proc = subprocess.run(
                TRAIN_CMD,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
        if proc.returncode == 0:
            st.success("Training finished. Reload the app to see metrics and forecasts.")
            st.code((proc.stdout or "").strip()[-4000:] or "(no stdout)")
        else:
            st.error("Training failed.")
            st.code((proc.stderr or proc.stdout or "").strip()[-8000:])


def _test_mae(exp: dict) -> tuple[float | None, float | None]:
    try:
        overall = exp["metrics"]["test"]["overall"]
        return overall["lightgbm"]["mae_kw"], overall["baseline"]["mae_kw"]
    except (KeyError, TypeError):
        return None, None


def tab_overview() -> None:
    models = artifacts.list_model_dirs()
    if not models:
        _no_models_panel()
        return

    latest = models[0]
    exp = artifacts.load_experiment(latest)
    if not exp:
        st.error(f"Missing experiment.json in `{artifacts.repo_relative(latest)}`.")
        return

    lgb_mae, base_mae = _test_mae(exp)
    n_files = artifacts.count_forecast_files(exp["model_version"])
    data_label = exp.get("data_label", "—")
    version = exp.get("model_version", latest.name)
    beats = exp.get("lightgbm_beats_baseline_on_test_mae")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Test MAE — LightGBM", f"{lgb_mae:.3f} kW" if lgb_mae is not None else "—")
    c2.metric("Test MAE — baseline", f"{base_mae:.3f} kW" if base_mae is not None else "—")
    c3.metric("Data label", data_label)
    c4.metric("Forecast CSV files", n_files)

    st.subheader("Latest model")
    st.write(
        f"**{version}** — stored at `{artifacts.repo_relative(latest)}`. "
        f"On the held-out test split, LightGBM "
        f"{'beats' if beats else 'does not beat'} the physics baseline on overall MAE."
    )

    if len(models) > 1:
        with st.expander("Older model versions"):
            for m in models[1:]:
                e = artifacts.load_experiment(m)
                if e:
                    lm, bm = _test_mae(e)
                    st.text(
                        f"{m.name}: LGBM MAE {lm:.3f} kW, baseline {bm:.3f} kW"
                        if lm is not None
                        else m.name
                    )
                else:
                    st.text(m.name)


def tab_forecast_day() -> None:
    models = artifacts.list_model_dirs()
    if not models:
        _no_models_panel()
        return

    versions = [artifacts.model_version_from_dir(m) for m in models]
    sites_df = artifacts.list_sites()
    if sites_df.empty:
        st.error("No sites in `forecasting/sites.example.csv`.")
        return

    name_to_id = dict(zip(sites_df["name"], sites_df["site_id"], strict=True))

    col1, col2, col3 = st.columns(3)
    version = col1.selectbox("Model version", versions)
    site_name = col2.selectbox("Site", list(name_to_id.keys()))
    site_id = name_to_id[site_name]

    days = artifacts.list_forecast_days(version, site_id)
    if not days:
        st.info(
            f"No forecast CSVs for **{site_name}** under `data/processed/forecasts/{version}/`. "
            "Train or re-run forecast export for this model."
        )
        return

    issue_day = col3.selectbox("Issue date (Colombo midnight)", days, index=len(days) - 1)

    df = artifacts.read_forecast_csv(version, site_id, issue_day)
    if df is None or df.empty:
        st.error("Could not read the forecast file.")
        return

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp")
    local = df["timestamp"].dt.tz_convert("Asia/Colombo")

    energies = artifacts.daily_energy_kwh(df)
    e1, e2, e3 = st.columns(3)
    e1.metric("Forecast energy (24 h)", f"{energies['model_kwh']:.2f} kWh")
    e2.metric("Baseline energy", f"{energies['baseline_kwh']:.2f} kWh")
    e3.metric("Nameplate cap (integral)", f"{energies['system_kwh']:.2f} kWh")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(local, df["pv_kw"], label="LightGBM pv_kw", color="#f4a261", linewidth=2)
    ax.plot(local, df["baseline_kw"], label="Physics baseline_kw", color="#2a9d8f", linewidth=1.5)
    ax.set_xlabel("Local time (Asia/Colombo)")
    ax.set_ylabel("AC power (kW)")
    ax.set_title(f"{site_name} · issue {issue_day} · {version}")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    st.pyplot(fig)
    plt.close(fig)

    st.subheader("Hourly table")
    show = df.copy()
    show["timestamp_local"] = local.dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(show, use_container_width=True, hide_index=True)

    csv_bytes = show.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download this day as CSV",
        data=csv_bytes,
        file_name=f"{site_id}_{issue_day}_{version}.csv",
        mime="text/csv",
    )


def tab_model_report() -> None:
    models = artifacts.list_model_dirs()
    if not models:
        _no_models_panel()
        return

    versions = [artifacts.model_version_from_dir(m) for m in models]
    version = st.selectbox("Model version", versions, key="report_version")
    model_dir = MODEL_DIR / version
    exp = artifacts.load_experiment(model_dir)
    md = artifacts.load_experiment_markdown(model_dir)

    if md:
        st.markdown(md)
    elif exp:
        st.subheader("Experiment summary")
        st.json(
            {
                "model_version": exp.get("model_version"),
                "data_label": exp.get("data_label"),
                "verdict": exp.get("verdict"),
                "lightgbm_beats_baseline_on_test_mae": exp.get(
                    "lightgbm_beats_baseline_on_test_mae"
                ),
            }
        )
        st.subheader("Test metrics")
        test = exp.get("metrics", {}).get("test", {})
        rows = []
        for slice_name, block in test.items():
            if not isinstance(block, dict):
                continue
            for model_name in ("lightgbm", "baseline"):
                m = block.get(model_name, {})
                rows.append(
                    {
                        "slice": slice_name,
                        "model": model_name,
                        "n": m.get("n"),
                        "mae_kw": m.get("mae_kw"),
                        "rmse_kw": m.get("rmse_kw"),
                        "nmae": m.get("nmae"),
                    }
                )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.error("No experiment.md or experiment.json for this version.")


overview, forecast_day, model_report = st.tabs(["Overview", "Forecast day", "Model report"])

with overview:
    tab_overview()
with forecast_day:
    tab_forecast_day()
with model_report:
    tab_model_report()