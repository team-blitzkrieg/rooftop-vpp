"""Hourly forecast and weekly retrain.

A failed site does not delete the last successful rows. Promotion of a
retrained model happens only when its holdout MAE beats the physics or
similar-hour baseline and the model currently marked Production.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from forecasting.config import WEATHER_CACHE_DIR
from serve.clock import floor_hour, parse_time
from serve.models import (
    predict_site,
    readings_frame,
    sites_frame,
    train_demand,
    train_pv,
)
from serve.registry import (
    load_production,
    production_mae,
    register_booster,
    should_promote,
)

logger = logging.getLogger(__name__)
TARGETS = ("pv", "demand", "net")


def run_forecast(store, *, now=None, weather_for=None, tracking_uri: str | None = None) -> dict:
    issued = floor_hour(now)
    try:
        pv_model, pv_version = load_production("pv", tracking_uri)
        demand_model, demand_version = load_production("demand", tracking_uri)
    except Exception as exc:
        logger.warning("No Production model, leaving the last forecast in place: %s", exc)
        return {"status": "no-model", "message": str(exc)}

    readings = readings_frame(store.all_readings())
    summary = []
    for site in store.list_sites():
        site_id = str(site["site_id"])
        try:
            weather = _weather(site, issued, weather_for)
            predicted = predict_site(
                site=site,
                readings=readings,
                weather=weather,
                issued_at=issued,
                pv_model=pv_model,
                demand_model=demand_model,
            )
            label, simulated = _label(readings, site_id)
            versions = {
                "pv": pv_version,
                "demand": demand_version,
                "net": f"pv={pv_version},demand={demand_version}",
            }
            for target in TARGETS:
                store.publish_success(
                    site_id,
                    target,
                    issued,
                    predicted[target],
                    model_version=versions[target],
                    data_label=label,
                    is_simulated=simulated,
                )
            summary.append({"site_id": site_id, "status": "success", "issued_at": issued.isoformat()})
            logger.info("Forecast %s issued %s pv=%s demand=%s", site_id, issued.isoformat(), pv_version, demand_version)
        except Exception as exc:
            logger.exception("Forecast failed for %s", site_id)
            for target in TARGETS:
                store.record_failure(site_id, target, str(exc), issued_at=issued)
            summary.append({"site_id": site_id, "status": "failed", "message": str(exc)})
    return {"status": "ok", "issued_at": issued.isoformat(), "sites": summary}


def run_retrain(
    store,
    *,
    weather: pd.DataFrame | None = None,
    tracking_uri: str | None = None,
    rounds: int = 40,
    promote_initial: bool = False,
) -> dict:
    readings = readings_frame(store.all_readings())
    sites = sites_frame(store.list_sites())
    if readings.empty or sites.empty:
        logger.info("Retrain skipped, no readings.")
        return {"status": "skipped", "message": "no readings"}
    days = readings["timestamp"].map(lambda stamp: parse_time(stamp).normalize()).nunique()
    if days < 7:
        logger.info("Retrain skipped, %s issue days.", days)
        return {"status": "skipped", "issue_days": int(days)}
    if weather is None:
        weather = _archive_weather(sites, readings)
    saved = []
    try:
        pv_model, pv_metrics = train_pv(readings, sites, weather, rounds=rounds)
        saved.append(_maybe_promote("pv", pv_model, pv_metrics, tracking_uri, promote_initial=promote_initial))
    except Exception as exc:
        logger.exception("PV retrain failed")
        saved.append({"target": "pv", "status": "failed", "message": str(exc)})
    try:
        demand_model, demand_metrics = train_demand(readings, weather, rounds=rounds)
        saved.append(_maybe_promote("demand", demand_model, demand_metrics, tracking_uri, promote_initial=promote_initial))
    except Exception as exc:
        logger.exception("Demand retrain failed")
        saved.append({"target": "demand", "status": "failed", "message": str(exc)})
    return {"status": "ok", "models": saved}


def _maybe_promote(name: str, booster, metrics: dict, tracking_uri: str | None, *, promote_initial: bool = False) -> dict:
    current = production_mae(name, tracking_uri)
    promote = should_promote(metrics.get("holdout_mae"), metrics.get("baseline_mae"), current)
    # The first Production alias has to exist or the API has nothing to serve.
    # Later versions still have to beat both the baseline and the current model.
    if promote_initial and current is None and metrics.get("holdout_mae") is not None:
        promote = True
    version = register_booster(booster, name, metrics, promote=promote, tracking_uri=tracking_uri)
    logger.info(
        "%s version %s promoted=%s holdout_mae=%s baseline_mae=%s current=%s",
        name,
        version,
        promote,
        metrics.get("holdout_mae"),
        metrics.get("baseline_mae"),
        current,
    )
    return {"target": name, "version": version, "promoted": promote, **metrics}


def _weather(site: dict, issued, weather_for):
    if weather_for is not None:
        return weather_for(site, issued)
    from forecasting.weather import fetch_weather

    start = issued.date()
    end = (issued + pd.Timedelta(hours=23)).date()
    frame = fetch_weather(
        pd.DataFrame([site]),
        start,
        end,
        kind="forecast",
        resolution="hourly",
        cache_dir=Path(WEATHER_CACHE_DIR),
    )
    return frame


def _archive_weather(sites: pd.DataFrame, readings: pd.DataFrame) -> pd.DataFrame:
    from forecasting.weather import fetch_weather

    start = parse_time(readings["timestamp"].min()).date()
    end = parse_time(readings["timestamp"].max()).date()
    return fetch_weather(
        sites,
        start,
        end,
        kind="historical",
        resolution="hourly",
        cache_dir=Path(WEATHER_CACHE_DIR),
    )


def _label(readings: pd.DataFrame, site_id: str) -> tuple[str, bool]:
    if readings.empty:
        return "MEASURED", False
    rows = readings.loc[readings["site_id"] == site_id]
    simulated = bool(rows["is_simulated"].any()) if "is_simulated" in rows.columns else False
    return ("SIMULATED" if simulated else "MEASURED"), simulated
