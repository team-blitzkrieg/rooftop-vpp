"""Fill a local database with SIMULATED readings and Production models.

Safe to run twice: if Dehiwala already has a PV forecast and both aliases
exist, it leaves them alone.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from forecasting.config import EXAMPLE_SITES
from forecasting.synthetic import generate_simulated
from forecasting.tables import load_sites
from serve.db import PostgresStore
from serve.jobs import run_forecast, run_retrain
from serve.log import configure_logging
from serve.models import add_simulated_consumption
from serve.registry import production_version
from serve.settings import load_settings

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    settings = load_settings()
    store = PostgresStore(settings.database_url)
    store.migrate()
    if production_version("pv") and production_version("demand") and store.latest_success("home-dehiwala", "pv"):
        logger.info("Seed data and Production models are already present.")
        return
    sites = load_sites(EXAMPLE_SITES)
    readings, weather = generate_simulated(
        sites,
        date(2024, 6, 1),
        date(2024, 6, 28),
        "hourly",
        seed=7,
    )
    readings = add_simulated_consumption(readings, weather, seed=7)
    _store_sites(store, sites)
    token = settings.device_token or "local-device-key"
    for site_id in sites["site_id"].astype(str):
        store.add_device(f"meter-{site_id}", site_id, f"{token}-{site_id}")
    for row in readings.itertuples(index=False):
        store.upsert_reading(
            str(row.site_id),
            row.timestamp,
            pv_kw=float(row.pv_kw) if pd.notna(row.pv_kw) else None,
            consumption_kw=float(row.consumption_kw) if pd.notna(row.consumption_kw) else None,
            data_label="SIMULATED",
            is_simulated=True,
        )
    logger.info("Stored %s simulated readings. Training.", len(readings))
    trained = run_retrain(store, weather=weather, rounds=40, promote_initial=True)
    if not production_version("pv") or not production_version("demand"):
        raise SystemExit(f"Training did not promote a Production model: {trained}")
    issued = pd.Timestamp("2024-06-28 00:00", tz="Asia/Colombo")
    result = run_forecast(
        store,
        now=issued.to_pydatetime(),
        weather_for=lambda site, issued_at: weather,
    )
    logger.info("Seed forecast: %s", result)
    failed = [item for item in result.get("sites", []) if item.get("status") != "success"]
    if failed:
        raise SystemExit(f"Seed forecast failed: {failed}")


def _store_sites(store, sites: pd.DataFrame) -> None:
    for row in sites.to_dict(orient="records"):
        store.upsert_site(row)


if __name__ == "__main__":
    main()
