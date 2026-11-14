"""MAE, RMSE and nMAE on kW, for the whole test set and two slices.

nMAE is MAE divided by the mean AC nameplate on the same rows. A cloudy day
is an issue-day whose daylight hours average at least 60% forecast cloud.
The cloudy score uses those daylight hours only. Midday is local hours 11, 12
and 13.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from forecasting.config import (
    CLOUDY_DAY_CLOUD_PCT,
    EVENING_END_MINUTE,
    EVENING_START_MINUTE,
    MIDDAY_HOURS,
    TIMEZONE,
)


def score(y_true, y_pred, denom) -> dict:
    actual = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    size = np.asarray(denom, dtype=float)
    ok = np.isfinite(actual) & np.isfinite(pred) & np.isfinite(size)
    n = int(ok.sum())
    if n == 0:
        return {"n": 0, "mae_kw": None, "rmse_kw": None, "nmae": None}
    error = pred[ok] - actual[ok]
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))
    denom = float(np.mean(size[ok]))
    nmae = float(mae / denom) if denom > 0 else None
    return {"n": n, "mae_kw": mae, "rmse_kw": rmse, "nmae": nmae}


def slice_masks(frame: pd.DataFrame, *, target: str = "pv") -> dict[str, np.ndarray]:
    if target == "demand":
        local = frame["timestamp"].dt.tz_convert(TIMEZONE)
        minute = local.dt.hour.to_numpy() * 60 + local.dt.minute.to_numpy()
        evening = (minute >= EVENING_START_MINUTE) & (minute < EVENING_END_MINUTE)
        weekend = local.dt.day_of_week.to_numpy() >= 5
        return {
            "overall": np.ones(len(frame), dtype=bool),
            "evening": evening,
            "weekend": weekend,
        }
    return _pv_slices(frame)


def _pv_slices(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    elevation = frame["solar_elevation_deg"].to_numpy(dtype=float)
    daylight = elevation > 0.0
    hour = frame["timestamp"].dt.tz_convert(TIMEZONE).dt.hour.to_numpy()
    midday = np.isin(hour, MIDDAY_HOURS)
    issued = pd.Series(frame["issued_at"])
    key = frame["site_id"].astype(str) + "|" + issued.dt.strftime("%Y-%m-%d")
    day = pd.DataFrame(
        {
            "key": key.to_numpy(),
            "cloud": frame["cloud_cover_pct"].to_numpy(dtype=float),
            "daylight": daylight,
        }
    )
    daylight_rows = day.loc[day["daylight"]]
    if daylight_rows.empty:
        cloudy = np.zeros(len(frame), dtype=bool)
    else:
        means = daylight_rows.groupby("key", sort=False)["cloud"].mean()
        cloudy_keys = set(means[means >= CLOUDY_DAY_CLOUD_PCT].index)
        cloudy = key.isin(cloudy_keys).to_numpy() & daylight
    return {
        "overall": np.ones(len(frame), dtype=bool),
        "cloudy": cloudy,
        "midday": midday,
    }
