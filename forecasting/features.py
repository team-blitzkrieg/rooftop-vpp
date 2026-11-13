"""Features that are known when the forecast is issued.

The issue time is local midnight. The row's timestamp is inside the next 24
hours. Lagged power is taken from a timestamp strictly before that midnight.
Same-day inverter readings are not features. Solar position is geometry, so
it is known ahead of time. Weather columns are the forecast, not a later
observation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from forecasting.baseline import solar_position
from forecasting.config import FEATURE_COLUMNS, TIMEZONE, WEATHER_COLUMNS
from forecasting.split import LeakageError
from forecasting.tables import align_weather


def build_frame(
    readings: pd.DataFrame,
    sites: pd.DataFrame,
    weather: pd.DataFrame,
) -> pd.DataFrame:
    if readings.empty or weather.empty:
        raise ValueError("Readings and weather are both required")
    sites = sites.copy()
    sites["site_id"] = sites["site_id"].astype(str)
    readings = readings.copy()
    readings["site_id"] = readings["site_id"].astype(str)
    weather = align_weather(weather, sites)
    weather["site_id"] = weather["site_id"].astype(str)

    missing_sites = sorted(set(readings["site_id"]) - set(sites["site_id"]))
    if missing_sites:
        raise ValueError(f"No site metadata for: {', '.join(missing_sites)}")

    geometry = [column for column in ("system_kw", "tilt_deg", "azimuth_deg", "latitude", "longitude") if column in readings.columns]
    readings = readings.drop(columns=geometry)
    site_keep = ["site_id", "system_kw", "tilt_deg", "azimuth_deg", "latitude", "longitude"]
    for optional in ("name", "location_id"):
        if optional in sites.columns:
            site_keep.append(optional)
    frame = readings.merge(sites[site_keep], on="site_id", how="left")

    weather_keep = ["site_id", "timestamp", *WEATHER_COLUMNS]
    for optional in ("is_simulated", "data_label", "weather_kind"):
        if optional in weather.columns:
            weather_keep.append(optional)
    weather_use = weather[weather_keep].drop_duplicates(["site_id", "timestamp"], keep="last")
    weather_use = weather_use.rename(
        columns={"is_simulated": "weather_simulated", "data_label": "weather_label"}
    )
    frame = frame.merge(weather_use, on=["site_id", "timestamp"], how="inner")
    if frame.empty:
        raise ValueError("Readings and weather share no site_id and timestamp")

    if "is_simulated" not in frame.columns:
        frame["is_simulated"] = False
    if "weather_simulated" not in frame.columns:
        frame["weather_simulated"] = False
    frame["is_simulated"] = frame["is_simulated"].astype(bool) | frame["weather_simulated"].astype(bool)
    frame["data_label"] = np.where(frame["is_simulated"], "SIMULATED", "MEASURED")

    local = frame["timestamp"].dt.tz_convert(TIMEZONE)
    frame["issued_at"] = local.dt.normalize()
    frame["hour"] = local.dt.hour + local.dt.minute / 60.0
    frame["day_of_year"] = local.dt.day_of_year.astype(int)
    frame = _add_solar(frame)
    frame = _add_lags(frame, readings)
    frame["lag_24h_norm"] = frame["lag_24h_kw"] / frame["system_kw"]
    frame["lag_48h_norm"] = frame["lag_48h_kw"] / frame["system_kw"]
    frame["recent_norm"] = frame["recent_kw"] / frame["system_kw"]
    frame = frame.sort_values(["site_id", "timestamp"]).reset_index(drop=True)
    assert_no_target_leakage(frame)
    return frame


def assert_no_target_leakage(frame: pd.DataFrame) -> None:
    """Fail if a lag timestamp is at or after the issue, or the horizon is not 24h."""
    required = ["issued_at", "timestamp", "lag_24h_at", "lag_48h_at", "recent_at"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise LeakageError(f"Cannot check leakage, missing {', '.join(missing)}")
    forbidden = {"pv_kw", "baseline_kw", "lag_24h_kw", "lag_48h_kw", "recent_kw"}
    if forbidden & set(FEATURE_COLUMNS):
        raise LeakageError("The model feature list includes the target or a raw lag in kW")
    lead = frame["timestamp"] - frame["issued_at"]
    if (lead < pd.Timedelta(0)).any() or (lead >= pd.Timedelta(hours=24)).any():
        raise LeakageError("A row sits outside the 24 hours that start at its issue time")
    for column in ("lag_24h_at", "lag_48h_at", "recent_at"):
        known = frame[column].notna()
        if known.any() and (frame.loc[known, column] >= frame.loc[known, "issued_at"]).any():
            raise LeakageError(f"{column} is not strictly before the issue time")


def infer_resolution(frame: pd.DataFrame) -> str:
    steps = []
    for _, group in frame.groupby("site_id", sort=False):
        diff = group["timestamp"].sort_values().diff().dropna()
        if diff.empty:
            continue
        steps.append(diff.median())
    if not steps:
        raise ValueError("Not enough timestamps to see the resolution")
    if any(step != steps[0] for step in steps):
        raise ValueError(f"Sites do not share one timestep: {steps}")
    step = steps[0]
    if step == pd.Timedelta(hours=1):
        return "hourly"
    if step == pd.Timedelta(minutes=15):
        return "15min"
    raise ValueError(f"Median step is {step}, expected 1 hour or 15 minutes")


def _add_solar(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in ("solar_zenith_deg", "solar_azimuth_deg", "solar_elevation_deg"):
        out[column] = np.nan
    for _, index in out.groupby("site_id", sort=False).groups.items():
        group = out.loc[index]
        position = solar_position(
            pd.DatetimeIndex(group["timestamp"]),
            float(group["latitude"].iloc[0]),
            float(group["longitude"].iloc[0]),
        )
        out.loc[index, "solar_zenith_deg"] = position["solar_zenith_deg"].to_numpy()
        out.loc[index, "solar_azimuth_deg"] = position["solar_azimuth_deg"].to_numpy()
        out.loc[index, "solar_elevation_deg"] = position["solar_elevation_deg"].to_numpy()
    return out


def _add_lags(frame: pd.DataFrame, readings: pd.DataFrame) -> pd.DataFrame:
    observed = readings.loc[:, ["site_id", "timestamp", "pv_kw"]].copy()
    observed["site_id"] = observed["site_id"].astype(str)
    observed["timestamp"] = pd.to_datetime(observed["timestamp"], utc=True).dt.tz_convert(TIMEZONE)
    out = frame.copy()
    for hours, kw_name, at_name in (
        (24, "lag_24h_kw", "lag_24h_at"),
        (48, "lag_48h_kw", "lag_48h_at"),
    ):
        lookup = observed.rename(columns={"timestamp": at_name, "pv_kw": kw_name})
        out[at_name] = out["timestamp"] - pd.Timedelta(hours=hours)
        out = out.drop(columns=[kw_name], errors="ignore")
        out = out.merge(lookup, on=["site_id", at_name], how="left")
        leaked = out[at_name].notna() & (out[at_name] >= out["issued_at"])
        out.loc[leaked, kw_name] = np.nan
        out.loc[leaked, at_name] = pd.NaT

    issues = out.loc[:, ["site_id", "issued_at"]].drop_duplicates()
    # merge_asof wants the time key in order across the whole frame, not per site.
    issues = issues.sort_values(["issued_at", "site_id"]).reset_index(drop=True)
    history = observed.rename(columns={"timestamp": "recent_at", "pv_kw": "recent_kw"})
    history = history.sort_values(["recent_at", "site_id"]).reset_index(drop=True)
    recent = pd.merge_asof(
        issues,
        history,
        left_on="issued_at",
        right_on="recent_at",
        by="site_id",
        direction="backward",
        allow_exact_matches=False,
    )
    out = out.drop(columns=["recent_kw", "recent_at"], errors="ignore")
    out = out.merge(recent, on=["site_id", "issued_at"], how="left")
    return out
