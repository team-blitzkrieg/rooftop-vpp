"""Write a simulated 48-hour forecast for the three example homes.

    python -m api.seed_demo

Manual only. It does not promote a model, does not upload an artefact, and
does not insert meter readings, so the weekly retrain is unchanged. A second
run replaces the previous demo rows.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from forecasting.baseline import baseline_power, similar_day_baseline
from forecasting.config import DEMAND_FEATURE_COLUMNS, EXAMPLE_SITES, FEATURE_COLUMNS, TIMEZONE
from forecasting.features import build_frame
from forecasting.model import predict_kw, train_and_evaluate
from forecasting.synthetic import generate_simulated
from forecasting.tables import load_sites, with_consumption

DEMO_MODEL_VERSION = "demo"
DEMO_SITES = ("home-dehiwala", "home-nugegoda", "home-moratuwa")
HORIZON_HOURS = 48
HISTORY_DAYS = 35
SITE_FIELDS = (
    "name",
    "timezone",
    "system_kw",
    "tilt_deg",
    "azimuth_deg",
    "latitude",
    "longitude",
    "has_meter",
    "demand_scale_kw",
)


def main() -> int:
    if not os.environ.get("DATABASE_URL", "").strip():
        print("DATABASE_URL is not set.")
        return 1
    from api.postgres import PostgresStore

    store = PostgresStore(os.environ["DATABASE_URL"])
    summary = seed_store(store)
    print(
        f"Demo forecast issued {summary['issued_at']} "
        f"for {summary['sites']} homes, {summary['rows']} rows, "
        f"model_version={DEMO_MODEL_VERSION}. promoted was not changed."
    )
    return 0


def seed_store(
    store,
    *,
    now=None,
    n_estimators: int = 80,
    history_days: int = HISTORY_DAYS,
) -> dict:
    """Insert any missing example homes and replace the demo forecast.

    `store.insert_model` is never called. Readings are not written.
    """
    sites = _example_sites()
    inserted = ensure_sites(store, sites)
    issued, bundles = build_demo_forecasts(
        sites,
        now=now,
        n_estimators=n_estimators,
        history_days=history_days,
    )
    promoted_before = _promoted_count(store)
    clear_demo(store, list(DEMO_SITES))
    written = 0
    for site_id, by_target in bundles.items():
        for target, rows in by_target.items():
            run_id = store.record_run(
                site_id,
                target,
                "success",
                issued_at=issued.isoformat(),
                model_version=DEMO_MODEL_VERSION,
            )
            store.publish_forecast(
                site_id,
                target,
                issued.isoformat(),
                rows,
                model_version=DEMO_MODEL_VERSION,
                run_id=run_id,
                resolution="hourly",
                data_label="SIMULATED",
                is_simulated=True,
            )
            written += len(rows)
    promoted_after = _promoted_count(store)
    if promoted_after != promoted_before:
        raise RuntimeError("The demo seed changed which model is promoted.")
    return {
        "issued_at": issued.isoformat(),
        "sites": len(bundles),
        "rows": written,
        "inserted_sites": inserted,
        "model_version": DEMO_MODEL_VERSION,
    }


def ensure_sites(store, sites: pd.DataFrame) -> list[str]:
    """Insert example homes that are not already in `sites`. Do not overwrite."""
    present = {row["site_id"] for row in store.list_sites()}
    inserted = []
    for record in sites.to_dict(orient="records"):
        site_id = str(record["site_id"])
        if site_id in present:
            continue
        fields = {}
        for name in SITE_FIELDS:
            if name not in record or pd.isna(record[name]):
                continue
            value = record[name]
            if name == "has_meter":
                value = bool(value)
            elif name in {"system_kw", "tilt_deg", "azimuth_deg", "latitude", "longitude", "demand_scale_kw"}:
                value = float(value)
            else:
                value = str(value)
            fields[name] = value
        store.add_site(site_id, **fields)
        inserted.append(site_id)
    return inserted


def clear_demo(store, site_ids: list[str]) -> None:
    """Drop the previous demo issue. Other model versions stay."""
    if hasattr(store, "forecasts") and isinstance(store.forecasts, list):
        wanted = set(site_ids)
        store.forecasts = [
            row
            for row in store.forecasts
            if not (row.get("model_version") == DEMO_MODEL_VERSION and row["site_id"] in wanted)
        ]
        store.runs = [
            row
            for row in store.runs
            if not (row.get("model_version") == DEMO_MODEL_VERSION and row["site_id"] in wanted)
        ]
        return
    with store._connect() as conn:
        conn.execute(
            "delete from forecasts where model_version = %s and site_id = any(%s)",
            (DEMO_MODEL_VERSION, site_ids),
        )
        conn.execute(
            "delete from forecast_runs where model_version = %s and site_id = any(%s)",
            (DEMO_MODEL_VERSION, site_ids),
        )
        conn.commit()


def build_demo_forecasts(
    sites: pd.DataFrame,
    *,
    now=None,
    n_estimators: int = 80,
    history_days: int = HISTORY_DAYS,
) -> tuple[pd.Timestamp, dict]:
    issued = _floor_hour(now)
    today = issued.date()
    history_end = today - timedelta(days=1)
    history_start = history_end - timedelta(days=history_days - 1)
    last_hour = issued + pd.Timedelta(hours=HORIZON_HOURS - 1)
    feature_start = today - timedelta(days=21)
    train_readings, train_weather = generate_simulated(
        sites, history_start, history_end, "hourly", seed=7
    )
    live_readings, live_weather = generate_simulated(
        sites, feature_start, last_hour.date(), "hourly", seed=7
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pv_model = _train(train_readings, sites, train_weather, "pv", root, n_estimators)
        demand_readings, messages = with_consumption(train_readings, sites)
        for message in messages:
            print(message)
        demand_model = _train(demand_readings, sites, train_weather, "demand", root, n_estimators)
        pv_frame = build_frame(live_readings, sites, live_weather, target="pv")
        demand_frame = build_frame(demand_readings_live(live_readings, sites), sites, live_weather, target="demand")
        hours = pd.date_range(issued, periods=HORIZON_HOURS, freq="1h")
        bundles = {}
        for site_id in sites["site_id"].astype(str):
            bundles[site_id] = _one_site(
                site_id,
                hours,
                issued,
                pv_frame,
                demand_frame,
                pv_model,
                demand_model,
            )
    return issued, bundles


def demand_readings_live(readings: pd.DataFrame, sites: pd.DataFrame) -> pd.DataFrame:
    kept, messages = with_consumption(readings, sites)
    for message in messages:
        print(message)
    return kept


def _train(readings, sites, weather, target: str, root: Path, n_estimators: int):
    frame = build_frame(readings, sites, weather, target=target)
    record = train_and_evaluate(
        frame,
        model_dir=root / target / "models",
        forecast_dir=root / target / "forecasts",
        n_estimators=n_estimators,
        early_stopping=min(20, n_estimators),
        target=target,
    )
    return lgb.Booster(model_file=record["paths"]["model"])


def _one_site(site_id, hours, issued, pv_frame, demand_frame, pv_model, demand_model) -> dict:
    wanted = {_hour_key(stamp) for stamp in hours}
    pv_part = _slice(pv_frame, site_id, wanted)
    demand_part = _slice(demand_frame, site_id, wanted)
    if len(pv_part) != HORIZON_HOURS or len(demand_part) != HORIZON_HOURS:
        raise RuntimeError(
            f"{site_id} has {len(pv_part)} PV hours and {len(demand_part)} demand hours, "
            f"expected {HORIZON_HOURS}"
        )
    pv_hat = predict_kw(pv_model, pv_part, feature_columns=list(FEATURE_COLUMNS), target="pv")
    demand_hat = predict_kw(
        demand_model,
        demand_part,
        feature_columns=list(DEMAND_FEATURE_COLUMNS),
        target="demand",
    )
    pv_base = baseline_power(pv_part).to_numpy(dtype=float)
    demand_base = similar_day_baseline(demand_frame.loc[demand_frame["site_id"] == site_id])
    demand_base = (
        demand_frame.loc[demand_frame["site_id"] == site_id]
        .assign(baseline_kw=demand_base.to_numpy())
        .pipe(lambda frame: _slice(frame, site_id, wanted)["baseline_kw"].to_numpy(dtype=float))
    )
    if not (np.isfinite(pv_hat).all() and np.isfinite(demand_hat).all()):
        raise RuntimeError(f"{site_id} forecast has a missing value")
    pv_rows = _rows(pv_part["timestamp"], issued, pv_hat, pv_base)
    demand_rows = _rows(demand_part["timestamp"], issued, demand_hat, demand_base)
    net_hat = np.round(demand_hat - pv_hat, 4)
    net_base = np.round(demand_base - pv_base, 4)
    net_rows = _rows(pv_part["timestamp"], issued, net_hat, net_base)
    return {"pv": pv_rows, "demand": demand_rows, "net": net_rows}


def _rows(timestamps, issued, values, baseline) -> list[dict]:
    rows = []
    for stamp, value, base in zip(timestamps, values, baseline, strict=True):
        stamp = pd.Timestamp(stamp).tz_convert(TIMEZONE)
        lead = (stamp - issued).total_seconds() / 3600.0
        rows.append(
            {
                "timestamp": stamp.isoformat(),
                "issued_at": issued.isoformat(),
                "lead_hours": lead,
                "value_kw": float(value),
                "baseline_kw": None if not np.isfinite(base) else float(base),
                "resolution": "hourly",
                "data_label": "SIMULATED",
                "is_simulated": True,
            }
        )
    return rows


def _slice(frame: pd.DataFrame, site_id: str, wanted: set[str]) -> pd.DataFrame:
    part = frame.loc[frame["site_id"].astype(str) == site_id].copy()
    part["_key"] = part["timestamp"].map(_hour_key)
    part = part.loc[part["_key"].isin(wanted)].drop_duplicates("_key").sort_values("_key")
    return part.reset_index(drop=True)


def _hour_key(stamp) -> str:
    return pd.Timestamp(stamp).tz_convert(TIMEZONE).floor("h").isoformat()


def _example_sites() -> pd.DataFrame:
    sites = load_sites(EXAMPLE_SITES)
    sites = sites.loc[sites["site_id"].isin(DEMO_SITES)].copy()
    missing = [site_id for site_id in DEMO_SITES if site_id not in set(sites["site_id"])]
    if missing:
        raise RuntimeError(f"Example sites file is missing {', '.join(missing)}")
    return sites.sort_values("site_id").reset_index(drop=True)


def _floor_hour(now) -> pd.Timestamp:
    stamp = pd.Timestamp(now if now is not None else datetime.now().astimezone())
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize(TIMEZONE)
    else:
        stamp = stamp.tz_convert(TIMEZONE)
    return stamp.floor("h")


def _promoted_count(store) -> int:
    if hasattr(store, "models") and isinstance(store.models, list):
        return sum(1 for row in store.models if row.get("promoted"))
    with store._connect() as conn:
        row = conn.execute("select count(*) from model_versions where promoted").fetchone()
    return int(row[0])


if __name__ == "__main__":
    raise SystemExit(main())
