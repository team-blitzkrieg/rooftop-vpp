"""Environment configuration. Secrets come from the environment, not from git."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str
    mlflow_tracking_uri: str
    api_key: str
    admin_api_key: str
    cors_origins: list[str]
    stale_after_minutes: int
    mqtt_url: str
    log_level: str
    device_token: str


def load_settings() -> Settings:
    stale = int(os.environ.get("STALE_AFTER_MINUTES", "120"))
    return Settings(
        database_url=os.environ.get("DATABASE_URL", "").strip(),
        mlflow_tracking_uri=os.environ.get("MLFLOW_TRACKING_URI", "").strip(),
        api_key=os.environ.get("API_KEY", "").strip(),
        admin_api_key=os.environ.get("ADMIN_API_KEY", "").strip(),
        cors_origins=_split_csv(os.environ.get("CORS_ORIGINS", "http://localhost:8000")),
        stale_after_minutes=stale,
        mqtt_url=os.environ.get("MQTT_URL", "").strip(),
        log_level=os.environ.get("LOG_LEVEL", "INFO").strip() or "INFO",
        device_token=os.environ.get("DEVICE_TOKEN", "").strip(),
    )
