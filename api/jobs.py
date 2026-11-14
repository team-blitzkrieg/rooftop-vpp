"""Scheduled forecast and retrain. GitHub Actions calls this.

    python -m api.jobs forecast
    python -m api.jobs retrain

If DATABASE_URL is unset the process logs that and exits 0, so a fork
without secrets is not a red build. The hourly job does not upload a model.
"""

from __future__ import annotations

import argparse
import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from api.registry import materialize_model, publish_artefact
from api.util import should_promote, test_mae
from forecasting.config import (
    BASELINE_LOSS_FACTOR,
    FORECAST_DIR,
    MODEL_DIR,
    TIMEZONE,
    WEATHER_CACHE_DIR,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.jobs")
    parser.add_argument("command", choices=["forecast", "retrain"])
    args = parser.parse_args(argv)
    if not os.environ.get("DATABASE_URL", "").strip():
        print("DATABASE_URL is not set. Skipping.")
        return 0
    from api.postgres import PostgresStore

    store = PostgresStore(os.environ["DATABASE_URL"])
    if args.command == "forecast":
        run_forecast(store)
    else:
        allow = os.environ.get("ALLOW_SYNTHETIC", "false").strip().lower() in {"1", "true", "yes"}
        run_retrain(store, allow_synthetic=allow)
    return 0


def run_forecast(store) -> dict:
    """Write today's forecast for each promoted target. A failure keeps the previous one."""
    summary = {"targets": []}
    for target in ("pv", "demand"):
        model = store.promoted_model(target)
        if model is None:
            print(f"No promoted {target} model. The last forecast stays.")
            summary["targets"].append({"target": target, "status": "no-model"})
            continue
        for site in store.list_sites():
            site_id = site["site_id"]
            try:
                _forecast_site(store, site, target, model)
                summary["targets"].append({"target": target, "site_id": site_id, "status": "success"})
            except Exception as exc:
                traceback.print_exc()
                store.record_run(
                    site_id,
                    target,
                    "failed",
                    model_version=model.get("version"),
                    message=str(exc),
                )
                summary["targets"].append(
                    {"target": target, "site_id": site_id, "status": "failed", "message": str(exc)}
                )
    return summary


def _forecast_site(store, site: dict, target: str, model: dict) -> None:
    import lightgbm as lgb

    from forecasting.baseline import baseline_power, similar_day_baseline
    from forecasting.features import build_frame, infer_resolution
    from forecasting.model import predict_kw
    from forecasting.weather import fetch_weather

    model_dir = materialize_model(model.get("artefact_url"), model["version"])
    experiment = json.loads((model_dir / "experiment.json").read_text(encoding="utf-8"))
    feature_file = model_dir / "features.json"
    feature_columns = json.loads(feature_file.read_text(encoding="utf-8")) if feature_file.exists() else None
    resolution = experiment["data_window"]["resolution"]
    raw_loss = experiment["baseline"].get("loss_factor")
    loss_factor = float(raw_loss) if raw_loss is not None else BASELINE_LOSS_FACTOR
    booster = lgb.Booster(model_file=str(model_dir / "model.txt"))

    readings = store.readings_for(site["site_id"], include_simulated=True)
    if len(readings) < 24:
        raise RuntimeError(f"{site['site_id']} has fewer than 24 readings")
    reading_frame = pd.DataFrame(readings)
    reading_frame["timestamp"] = pd.to_datetime(reading_frame["timestamp"], utc=True).dt.tz_convert(TIMEZONE)
    sites = pd.DataFrame([site])
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    weather = fetch_weather(
        sites,
        today,
        today,
        kind="forecast",
        resolution=resolution,
        cache_dir=WEATHER_CACHE_DIR,
    )
    frame = build_frame(reading_frame, sites, weather, target=target)
    if target == "demand":
        frame["baseline_kw"] = similar_day_baseline(frame).to_numpy()
    issued = pd.Timestamp(datetime(today.year, today.month, today.day), tz=TIMEZONE)
    day_frame = frame.loc[frame["issued_at"] == issued].copy()
    if day_frame.empty:
        raise RuntimeError(f"No joined rows for {site['site_id']} on {today.isoformat()}")
    if infer_resolution(day_frame) != resolution:
        raise RuntimeError("Reading resolution does not match the promoted model")
    if target == "pv":
        day_frame["baseline_kw"] = baseline_power(day_frame, loss_factor).to_numpy()
    predicted = predict_kw(booster, day_frame, feature_columns=feature_columns, target=target)
    label = "SIMULATED" if bool(day_frame["is_simulated"].any()) else "MEASURED"
    net_values = None
    if target == "demand":
        net_values = predicted - baseline_power(day_frame).to_numpy(dtype=float)
    rows = []
    for index, value in enumerate(predicted.tolist()):
        stamp = day_frame["timestamp"].iloc[index]
        lead = (stamp - day_frame["issued_at"].iloc[index]).total_seconds() / 3600.0
        rows.append(
            {
                "timestamp": stamp.isoformat(),
                "issued_at": issued.isoformat(),
                "lead_hours": lead,
                "value_kw": value,
                "baseline_kw": float(day_frame["baseline_kw"].iloc[index]),
                "net_kw": None if net_values is None else float(net_values[index]),
                "resolution": resolution,
                "data_label": label,
                "is_simulated": label == "SIMULATED",
            }
        )
    run_id = store.record_run(
        site["site_id"],
        target,
        "success",
        issued_at=issued.isoformat(),
        model_version=model.get("version"),
    )
    store.publish_forecast(
        site["site_id"],
        target,
        issued.isoformat(),
        rows,
        model_version=model["version"],
        run_id=run_id,
        resolution=resolution,
        data_label=label,
        is_simulated=label == "SIMULATED",
    )


def run_retrain(store, *, allow_synthetic: bool = False, trainer=None) -> dict:
    """Weekly fit. Synthetic rows are ignored unless a manual run asks for them.

    Fewer than three issue days keeps the promoted model. A worse test MAE
    is stored and not promoted. Readings older than 90 days and forecast
    points older than 30 days are deleted, except the latest successful issue.
    """
    days = store.issue_day_count(include_simulated=allow_synthetic)
    if days < 3:
        print(
            f"{days} issue day(s) of "
            f"{'any' if allow_synthetic else 'measured'} readings. "
            "Keeping the promoted model."
        )
        store.prune()
        return {"status": "skipped", "issue_days": days}
    if trainer is None:
        trainer = _train_from_store
    try:
        records = trainer(store, allow_synthetic=allow_synthetic)
    except Exception as exc:
        traceback.print_exc()
        store.prune()
        return {"status": "failed", "message": str(exc)}
    if isinstance(records, dict):
        records = [records]
    saved = []
    for record in records:
        target = record.get("forecast_target", "pv")
        new_mae = test_mae(record.get("metrics"))
        current = store.promoted_model(target)
        current_mae = test_mae(current.get("metrics") if current else None)
        promoted = should_promote(new_mae, current_mae)
        artefact_url = None
        model_file = (record.get("paths") or {}).get("model")
        if model_file:
            artefact_url = publish_artefact(Path(model_file).parent)
        store.insert_model(
            record["model_version"],
            target,
            record.get("metrics"),
            promoted=promoted,
            artefact_url=artefact_url,
            git_sha=record.get("git_sha"),
        )
        saved.append({"version": record["model_version"], "promoted": promoted, "target": target})
        print(f"{record['model_version']} promoted={promoted} test MAE {new_mae} against {current_mae}.")
    store.prune()
    return {"status": "trained", "models": saved}


def _train_from_store(store, *, allow_synthetic: bool) -> list[dict]:
    from forecasting.features import build_frame
    from forecasting.model import train_and_evaluate
    from forecasting.tables import with_consumption
    from forecasting.weather import fetch_weather

    sites = pd.DataFrame(store.list_sites())
    if sites.empty or sites["latitude"].isna().all():
        raise RuntimeError("Sites need latitude and longitude before a retrain")
    frames = []
    for site_id in sites["site_id"].astype(str):
        rows = store.readings_for(site_id, include_simulated=allow_synthetic)
        if rows:
            frames.append(pd.DataFrame(rows))
    if not frames:
        raise RuntimeError("No readings to train on")
    readings = pd.concat(frames, ignore_index=True)
    readings["timestamp"] = pd.to_datetime(readings["timestamp"], utc=True).dt.tz_convert(TIMEZONE)
    weather = fetch_weather(
        sites,
        readings["timestamp"].min().date(),
        readings["timestamp"].max().date(),
        kind="historical",
        resolution="hourly",
        cache_dir=WEATHER_CACHE_DIR,
    )
    records = []
    errors = []
    try:
        pv_frame = build_frame(readings, sites, weather, target="pv")
        records.append(
            train_and_evaluate(pv_frame, model_dir=MODEL_DIR, forecast_dir=FORECAST_DIR, target="pv")
        )
    except (ValueError, RuntimeError) as exc:
        errors.append(f"pv: {exc}")
        print(f"Skipping pv retrain: {exc}")
    try:
        demand_readings, messages = with_consumption(readings, sites)
        for message in messages:
            print(message)
        demand_frame = build_frame(demand_readings, sites, weather, target="demand")
        records.append(
            train_and_evaluate(
                demand_frame,
                model_dir=MODEL_DIR,
                forecast_dir=FORECAST_DIR,
                target="demand",
            )
        )
    except (ValueError, RuntimeError) as exc:
        errors.append(f"demand: {exc}")
        print(f"Skipping demand retrain: {exc}")
    if not records:
        raise RuntimeError("; ".join(errors) or "Neither target could be trained")
    return records


if __name__ == "__main__":
    raise SystemExit(main())
