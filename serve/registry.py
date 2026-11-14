"""MLflow model registry. Tracking is in Postgres; artefacts are local or S3.

There is no separate MLflow host in front of the pilot. The compose file runs
`mlflow server` on the docker network. Set MLFLOW_S3_ENDPOINT_URL and an
s3:// artefact root on the server when the disk should not hold the files.
"""

from __future__ import annotations

import os

import mlflow
from mlflow.tracking import MlflowClient

PRODUCTION = "production"


def use_tracking(uri: str | None) -> str:
    tracking = uri or os.environ.get("MLFLOW_TRACKING_URI", "").strip() or "sqlite:///mlflow.db"
    mlflow.set_tracking_uri(tracking)
    return tracking


def register_booster(booster, name: str, metrics: dict, *, promote: bool, tracking_uri: str | None = None) -> str:
    use_tracking(tracking_uri)
    with mlflow.start_run(run_name=name):
        numbers = {key: float(value) for key, value in metrics.items() if value is not None}
        if numbers:
            mlflow.log_metrics(numbers)
        logged = mlflow.lightgbm.log_model(
            booster,
            name="model",
            registered_model_name=name,
        )
    version = str(logged.registered_model_version)
    client = MlflowClient()
    for key, value in numbers.items():
        client.set_model_version_tag(name, version, key, f"{value:.8f}")
    if promote:
        client.set_registered_model_alias(name, PRODUCTION, version)
    return version


def production_version(name: str, tracking_uri: str | None = None):
    use_tracking(tracking_uri)
    client = MlflowClient()
    try:
        return client.get_model_version_by_alias(name, PRODUCTION)
    except Exception:
        return None


def production_mae(name: str, tracking_uri: str | None = None) -> float | None:
    version = production_version(name, tracking_uri)
    if version is None:
        return None
    raw = (version.tags or {}).get("holdout_mae")
    if raw is None:
        return None
    return float(raw)


def load_production(name: str, tracking_uri: str | None = None):
    use_tracking(tracking_uri)
    version = production_version(name, tracking_uri)
    if version is None:
        raise RuntimeError(f"No Production model for {name}")
    booster = mlflow.lightgbm.load_model(f"models:/{name}@{PRODUCTION}")
    return booster, str(version.version)


def should_promote(new_mae: float | None, baseline_mae: float | None, current_mae: float | None) -> bool:
    """A new version is promoted only when it beats the baseline and the current model.

    With no current Production model, beating the baseline is enough.
    """
    if new_mae is None or baseline_mae is None:
        return False
    if not (new_mae < baseline_mae):
        return False
    if current_mae is None:
        return True
    return new_mae < current_mae
