"""Small helpers shared by the API and the stores."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pandas as pd

from forecasting.config import TIMEZONE


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def parse_time(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize(TIMEZONE)
    else:
        stamp = stamp.tz_convert(TIMEZONE)
    return stamp


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_mae(metrics: dict | None) -> float | None:
    if not metrics:
        return None
    try:
        value = metrics["test"]["overall"]["lightgbm"]["mae_kw"]
    except (KeyError, TypeError):
        return None
    if value is None:
        return None
    return float(value)


def should_promote(new_mae: float | None, current_mae: float | None) -> bool:
    """Promote only when the new test MAE is better than the model already in use."""
    if new_mae is None:
        return False
    if current_mae is None:
        return True
    return new_mae < current_mae
