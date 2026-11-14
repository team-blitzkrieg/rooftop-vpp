"""Load the Production models and write the next 24 hours, on a schedule."""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from serve.db import PostgresStore
from serve.jobs import run_forecast, run_retrain
from serve.log import configure_logging
from serve.mqtt import start_bridge
from serve.settings import load_settings

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    settings = load_settings()
    store = PostgresStore(settings.database_url)
    store.migrate()

    def on_mqtt(body: dict) -> None:
        site_id = store.site_for_token(body["device_token"])
        if site_id is None:
            logger.warning("MQTT device token was rejected")
            return
        store.upsert_reading(
            site_id,
            body["timestamp"],
            pv_kw=body.get("pv_kw"),
            consumption_kw=body.get("consumption_kw"),
            import_kw=body.get("import_kw"),
            export_kw=body.get("export_kw"),
        )

    start_bridge(settings.mqtt_url, on_mqtt)
    scheduler = BlockingScheduler(timezone="Asia/Colombo")
    scheduler.add_job(lambda: run_forecast(store), "cron", minute=5, id="hourly-forecast")
    scheduler.add_job(lambda: run_retrain(store), "cron", day_of_week="sun", hour=18, minute=30, id="weekly-retrain")
    logger.info("Worker scheduled. Hourly forecast at :05, retrain Monday 00:00 Asia/Colombo.")
    scheduler.start()


if __name__ == "__main__":
    main()
