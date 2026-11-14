"""Load PV forecast artefacts from the repo tree (paths relative to REPO_ROOT)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from forecasting.config import EXAMPLE_SITES, FORECAST_DIR, MODEL_DIR, REPO_ROOT

MODEL_PREFIX = "pv-lgbm-"


def list_model_dirs() -> list[Path]:
    root = Path(MODEL_DIR)
    if not root.is_dir():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir() and p.name.startswith(MODEL_PREFIX)]
    dirs.sort(key=lambda p: p.name, reverse=True)
    return dirs


def load_experiment(model_dir: Path) -> dict | None:
    path = Path(model_dir) / "experiment.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_experiment_markdown(model_dir: Path) -> str | None:
    path = Path(model_dir) / "experiment.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def model_version_from_dir(model_dir: Path) -> str:
    return Path(model_dir).name


def forecast_root(model_version: str) -> Path:
    return Path(FORECAST_DIR) / model_version


def list_sites() -> pd.DataFrame:
    path = Path(EXAMPLE_SITES)
    if not path.is_file():
        return pd.DataFrame(columns=["site_id", "name"])
    return pd.read_csv(path)


def list_forecast_days(model_version: str, site_id: str) -> list[str]:
    site_dir = forecast_root(model_version) / site_id
    if not site_dir.is_dir():
        return []
    days = sorted(p.stem for p in site_dir.glob("*.csv"))
    return days


def read_forecast_csv(model_version: str, site_id: str, issue_day: str) -> pd.DataFrame | None:
    path = forecast_root(model_version) / site_id / f"{issue_day}.csv"
    if not path.is_file():
        return None
    return pd.read_csv(path)


def count_forecast_files(model_version: str) -> int:
    base = Path(FORECAST_DIR) / model_version
    if not base.is_dir():
        return 0
    return sum(1 for _ in base.rglob("*.csv"))


def daily_energy_kwh(frame: pd.DataFrame) -> dict[str, float]:
    """Integrate kW to kWh using timestamp spacing (handles hourly and 15 min)."""
    if frame.empty:
        return {"model_kwh": 0.0, "baseline_kwh": 0.0, "system_kwh": 0.0}
    work = frame.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True)
    work = work.sort_values("timestamp")
    delta_h = work["timestamp"].diff().dt.total_seconds() / 3600.0
    if delta_h.isna().all():
        return {"model_kwh": 0.0, "baseline_kwh": 0.0, "system_kwh": 0.0}
    hours = delta_h.fillna(delta_h.median())
    if hours.isna().all() or hours.max() <= 0:
        res = work.get("resolution", pd.Series(["hourly"])).iloc[0]
        hours = pd.Series(0.25 if res == "15min" else 1.0, index=work.index)
    model = float((work["pv_kw"] * hours).sum())
    baseline = float((work["baseline_kw"] * hours).sum())
    system = float((work["system_kw"] * hours).sum())
    return {"model_kwh": model, "baseline_kwh": baseline, "system_kwh": system}


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)