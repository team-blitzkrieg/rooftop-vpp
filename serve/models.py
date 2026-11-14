"""Build the next 24 hourly rows and score a holdout.

PV uses the existing LightGBM contract in `forecasting` (features known at
issue time, output in kW, night forced to zero). Demand is a separate
registry model trained on `consumption_kw`. The research demand pipeline
lives on its own branch; this service only needs a model that speaks this
feature list.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from forecasting.baseline import baseline_power, solar_position
from forecasting.config import FEATURE_COLUMNS, TIMEZONE
from forecasting.features import build_frame
from forecasting.model import predict_kw
from serve.clock import parse_time

DEMAND_FEATURES = [
    "hour",
    "day_of_year",
    "day_of_week",
    "is_weekend",
    "temp_c",
    "lag_24h_kw",
    "recent_kw",
]

LGB_PARAMS = {
    "objective": "regression",
    "metric": "l1",
    "learning_rate": 0.08,
    "num_leaves": 15,
    "min_child_samples": 10,
    "verbosity": -1,
    "seed": 7,
    "num_threads": 1,
    "force_row_wise": True,
    "deterministic": True,
}


def readings_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["site_id"] = frame["site_id"].astype(str)
    frame["timestamp"] = frame["timestamp"].map(parse_time)
    return frame


def sites_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["site_id"] = frame["site_id"].astype(str)
    return frame


def train_pv(readings: pd.DataFrame, sites: pd.DataFrame, weather: pd.DataFrame, *, rounds: int = 40) -> tuple[lgb.Booster, dict]:
    frame = build_frame(readings, sites, weather)
    return _train_split(frame, feature_columns=list(FEATURE_COLUMNS), target="pv", rounds=rounds)


def train_demand(readings: pd.DataFrame, weather: pd.DataFrame, *, rounds: int = 40) -> tuple[lgb.Booster, dict]:
    frame = _demand_history(readings, weather)
    return _train_split(frame, feature_columns=list(DEMAND_FEATURES), target="demand", rounds=rounds)


def predict_site(
    *,
    site: dict,
    readings: pd.DataFrame,
    weather: pd.DataFrame,
    issued_at,
    pv_model,
    demand_model,
) -> dict[str, list[dict]]:
    issued = parse_time(issued_at).floor("h")
    site_id = str(site["site_id"])
    history = readings.loc[readings["site_id"] == site_id].copy()
    hours = pd.date_range(issued, periods=24, freq="1h")
    weather_site = _weather_for(weather, site_id, hours)
    pv_frame = _pv_horizon(site, history, weather_site, hours, issued)
    demand_frame = _demand_horizon(history, weather_site, hours, issued)
    pv_values = predict_kw(pv_model, pv_frame)
    demand_values = np.clip(np.asarray(demand_model.predict(demand_frame[DEMAND_FEATURES]), dtype=float), 0.0, None)
    demand_values = np.round(demand_values, 4)
    pv_rows = [_point(ts, value) for ts, value in zip(hours, pv_values, strict=True)]
    demand_rows = [_point(ts, value) for ts, value in zip(hours, demand_values, strict=True)]
    net_rows = [
        _point(pv["timestamp"], round(float(demand["value_kw"]) - float(pv["value_kw"]), 4))
        for pv, demand in zip(pv_rows, demand_rows, strict=True)
    ]
    return {"pv": pv_rows, "demand": demand_rows, "net": net_rows}


def _train_split(frame: pd.DataFrame, *, feature_columns: list[str], target: str, rounds: int):
    frame = frame.copy()
    frame["issue_day"] = frame["timestamp"].dt.tz_convert(TIMEZONE).dt.normalize()
    days = list(frame["issue_day"].drop_duplicates().sort_values())
    if len(days) < 5:
        raise RuntimeError(f"Need at least 5 issue days to train {target}, found {len(days)}")
    cut = max(1, int(len(days) * 0.8))
    if cut >= len(days):
        cut = len(days) - 1
    train_days = set(days[:cut])
    hold_days = set(days[cut:])
    train = frame.loc[frame["issue_day"].isin(train_days)]
    hold = frame.loc[frame["issue_day"].isin(hold_days)]
    train_y = _target(train, target)
    booster = lgb.train(
        LGB_PARAMS,
        lgb.Dataset(train[feature_columns], label=train_y, feature_name=feature_columns),
        num_boost_round=int(rounds),
    )
    if target == "pv":
        predicted = predict_kw(booster, hold)
        actual = hold["pv_kw"].to_numpy(dtype=float)
        baseline = baseline_power(hold).to_numpy(dtype=float)
    else:
        predicted = np.clip(booster.predict(hold[feature_columns]), 0.0, None)
        actual = hold["consumption_kw"].to_numpy(dtype=float)
        baseline = _demand_baseline(frame, hold)
    return booster, {
        "holdout_mae": _mae(actual, predicted),
        "baseline_mae": _mae(actual, baseline),
    }


def _target(frame: pd.DataFrame, target: str) -> np.ndarray:
    if target == "pv":
        return frame["pv_kw"].to_numpy(dtype=float) / frame["system_kw"].to_numpy(dtype=float)
    return frame["consumption_kw"].to_numpy(dtype=float)


def _mae(actual, predicted) -> float | None:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    ok = np.isfinite(actual) & np.isfinite(predicted)
    if not ok.any():
        return None
    return float(np.mean(np.abs(predicted[ok] - actual[ok])))


def _demand_baseline(history: pd.DataFrame, hold: pd.DataFrame) -> np.ndarray:
    """Mean of the same clock hour on earlier days. Not negative."""
    hist = history.copy()
    local = hist["timestamp"].dt.tz_convert(TIMEZONE)
    hist["hour_key"] = local.dt.hour
    out = []
    for _, row in hold.iterrows():
        stamp = row["timestamp"]
        earlier = hist.loc[
            (hist["site_id"] == row["site_id"])
            & (hist["hour_key"] == stamp.tz_convert(TIMEZONE).hour)
            & (hist["timestamp"] < stamp)
            & (hist["timestamp"] >= stamp - pd.Timedelta(days=28))
        ]
        values = earlier["consumption_kw"].to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        out.append(float(np.mean(values)) if len(values) else np.nan)
    return np.clip(np.asarray(out, dtype=float), 0.0, None)


def _demand_history(readings: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for site_id, group in readings.groupby("site_id", sort=False):
        group = group.sort_values("timestamp")
        weather_site = weather.loc[weather["site_id"].astype(str) == str(site_id)] if "site_id" in weather.columns else weather
        keyed = weather_site.copy()
        keyed["key"] = keyed["timestamp"].map(lambda value: _hour_key(value))
        temp = keyed.drop_duplicates("key", keep="last").set_index("key")["temp_c"]
        for _, row in group.iterrows():
            stamp = parse_time(row["timestamp"])
            issued = stamp.tz_convert(TIMEZONE).normalize()
            past = group.loc[group["timestamp"] < issued]
            recent = past["consumption_kw"].dropna()
            lag_stamp = stamp - pd.Timedelta(hours=24)
            lag_hit = group.loc[group["timestamp"] == lag_stamp, "consumption_kw"]
            rows.append(
                {
                    "site_id": str(site_id),
                    "timestamp": stamp,
                    "consumption_kw": row["consumption_kw"],
                    "hour": stamp.tz_convert(TIMEZONE).hour + stamp.tz_convert(TIMEZONE).minute / 60.0,
                    "day_of_year": int(stamp.tz_convert(TIMEZONE).day_of_year),
                    "day_of_week": int(stamp.tz_convert(TIMEZONE).day_of_week),
                    "is_weekend": float(stamp.tz_convert(TIMEZONE).day_of_week >= 5),
                    "temp_c": _temp_at(temp, stamp),
                    "lag_24h_kw": float(lag_hit.iloc[-1]) if len(lag_hit) else np.nan,
                    "recent_kw": float(recent.iloc[-1]) if len(recent) else np.nan,
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("No consumption rows to train on")
    return frame


def _pv_horizon(site, history, weather_site, hours, issued) -> pd.DataFrame:
    past = history.loc[history["timestamp"] < issued].sort_values("timestamp")
    recent = float(past["pv_kw"].dropna().iloc[-1]) if past["pv_kw"].notna().any() else np.nan
    system_kw = float(site["system_kw"])
    position = solar_position(
        pd.DatetimeIndex(hours),
        float(site["latitude"]),
        float(site["longitude"]),
    )
    temp = weather_site
    rows = []
    for index, stamp in enumerate(hours):
        lag24 = stamp - pd.Timedelta(hours=24)
        lag48 = stamp - pd.Timedelta(hours=48)
        weather_row = temp.loc[_hour_key(stamp)] if _hour_key(stamp) in temp.index else None
        if weather_row is None:
            raise RuntimeError(f"No weather at {stamp.isoformat()}")
        rows.append(
            {
                "site_id": str(site["site_id"]),
                "timestamp": stamp,
                "system_kw": system_kw,
                "tilt_deg": float(site["tilt_deg"]),
                "azimuth_deg": float(site["azimuth_deg"]),
                "hour": stamp.hour + stamp.minute / 60.0,
                "day_of_year": int(stamp.day_of_year),
                "solar_zenith_deg": float(position["solar_zenith_deg"].iloc[index]),
                "solar_azimuth_deg": float(position["solar_azimuth_deg"].iloc[index]),
                "solar_elevation_deg": float(position["solar_elevation_deg"].iloc[index]),
                "ghi_wm2": float(weather_row["ghi_wm2"]),
                "dni_wm2": float(weather_row["dni_wm2"]),
                "dhi_wm2": float(weather_row["dhi_wm2"]),
                "cloud_cover_pct": float(weather_row["cloud_cover_pct"]),
                "temp_c": float(weather_row["temp_c"]),
                "lag_24h_norm": _kw_at(history, lag24, "pv_kw") / system_kw,
                "lag_48h_norm": _kw_at(history, lag48, "pv_kw") / system_kw,
                "recent_norm": recent / system_kw,
            }
        )
    return pd.DataFrame(rows)


def _demand_horizon(history, weather_site, hours, issued) -> pd.DataFrame:
    past = history.loc[history["timestamp"] < issued].sort_values("timestamp")
    recent_series = past["consumption_kw"].dropna() if "consumption_kw" in past.columns else pd.Series(dtype=float)
    recent = float(recent_series.iloc[-1]) if len(recent_series) else np.nan
    temp = weather_site["temp_c"]
    rows = []
    for stamp in hours:
        local = stamp.tz_convert(TIMEZONE)
        rows.append(
            {
                "timestamp": stamp,
                "hour": local.hour + local.minute / 60.0,
                "day_of_year": int(local.day_of_year),
                "day_of_week": int(local.day_of_week),
                "is_weekend": float(local.day_of_week >= 5),
                "temp_c": _temp_at(temp, stamp),
                "lag_24h_kw": _kw_at(history, stamp - pd.Timedelta(hours=24), "consumption_kw"),
                "recent_kw": recent,
            }
        )
    frame = pd.DataFrame(rows)
    if frame["temp_c"].isna().any():
        raise RuntimeError("Demand forecast is missing temperature")
    return frame


def _weather_for(weather: pd.DataFrame, site_id: str, hours: pd.DatetimeIndex) -> pd.DataFrame:
    frame = weather.copy()
    frame["timestamp"] = frame["timestamp"].map(lambda value: parse_time(value).floor("h"))
    if "site_id" in frame.columns:
        frame = frame.loc[frame["site_id"].astype(str) == str(site_id)]
    frame["key"] = frame["timestamp"].map(_hour_key)
    frame = frame.drop_duplicates("key", keep="last").set_index("key")
    missing = [stamp for stamp in hours if _hour_key(stamp) not in frame.index]
    if missing:
        raise RuntimeError(f"Weather is missing {len(missing)} forecast hours, first {missing[0]}")
    return frame


def _hour_key(stamp) -> str:
    return parse_time(stamp).floor("h").isoformat()


def _temp_at(series: pd.Series, stamp) -> float:
    key = _hour_key(stamp)
    if key not in series.index and stamp in series.index:
        key = stamp
    if key not in series.index:
        return np.nan
    value = series.loc[key]
    if isinstance(value, pd.Series):
        value = value.iloc[-1]
    return float(value)


def _kw_at(history: pd.DataFrame, stamp, column: str) -> float:
    if column not in history.columns:
        return np.nan
    hit = history.loc[history["timestamp"] == stamp, column]
    if hit.empty or pd.isna(hit.iloc[-1]):
        return np.nan
    return float(hit.iloc[-1])


def _point(stamp, value: float) -> dict:
    return {"timestamp": parse_time(stamp).isoformat(), "value_kw": float(value)}


def add_simulated_consumption(readings: pd.DataFrame, weather: pd.DataFrame, *, seed: int = 7) -> pd.DataFrame:
    """Serving seed only. Labelled SIMULATED. Not a household meter.

    Weekdays peak near 07:00 and 20:00. Weekends move the morning later.
    Hot hours add a little load. The research demand model is a separate piece.
    """
    rng = np.random.default_rng(seed)
    out = readings.copy()
    out["timestamp"] = out["timestamp"].map(parse_time)
    weather = weather.copy()
    weather["timestamp"] = weather["timestamp"].map(parse_time)
    temp = weather[["site_id", "timestamp", "temp_c"]] if "site_id" in weather.columns else weather[["timestamp", "temp_c"]]
    merged = out.merge(temp, on=["site_id", "timestamp"] if "site_id" in temp.columns else ["timestamp"], how="left")
    local = merged["timestamp"].dt.tz_convert(TIMEZONE)
    hour = local.dt.hour.to_numpy(dtype=float) + local.dt.minute.to_numpy(dtype=float) / 60.0
    weekend = local.dt.day_of_week.to_numpy() >= 5
    morning = np.where(weekend, _bump(hour, 9.5, 1.6, 0.45), _bump(hour, 7.0, 1.1, 0.55))
    evening = np.where(weekend, _bump(hour, 20.0, 1.3, 1.05), _bump(hour, 20.0, 1.2, 0.95))
    heat = 0.04 * np.clip(merged["temp_c"].to_numpy(dtype=float) - 26.0, 0.0, None)
    scale = np.where(merged["site_id"].astype(str) == "home-moratuwa", 1.6, 1.0)
    load = (0.2 + morning + evening + heat) * scale
    load = load + rng.normal(0.0, 0.03, size=len(merged))
    out["consumption_kw"] = np.round(np.clip(load, 0.0, None), 4)
    return out


def _bump(hour: np.ndarray, center: float, width: float, amp: float) -> np.ndarray:
    return amp * np.exp(-0.5 * ((hour - center) / width) ** 2)
