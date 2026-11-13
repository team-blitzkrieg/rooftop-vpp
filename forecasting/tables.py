"""Read site metadata and edge-unit readings, and write tables with a sidecar."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from forecasting.config import READING_COLUMNS, SITE_COLUMNS, TIMEZONE, WEATHER_COLUMNS


def to_colombo(values) -> pd.Series:
    parsed = pd.to_datetime(pd.Series(values))
    if parsed.dt.tz is None:
        parsed = parsed.dt.tz_localize(TIMEZONE)
    else:
        parsed = parsed.dt.tz_convert(TIMEZONE)
    return parsed


def load_sites(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = [column for column in SITE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing site columns: {', '.join(missing)}")
    out = frame.copy()
    out["site_id"] = out["site_id"].astype(str)
    for column in ("system_kw", "tilt_deg", "azimuth_deg", "latitude", "longitude"):
        out[column] = pd.to_numeric(out[column])
    if out["site_id"].duplicated().any():
        raise ValueError(f"{path} has a repeated site_id")
    if (~np.isfinite(out["system_kw"])).any() or (out["system_kw"] <= 0).any():
        raise ValueError("system_kw must be a positive number")
    if ((out["tilt_deg"] < 0) | (out["tilt_deg"] > 90)).any():
        raise ValueError("tilt_deg must be between 0 and 90")
    if ((out["azimuth_deg"] < 0) | (out["azimuth_deg"] > 360)).any():
        raise ValueError("azimuth_deg must be between 0 and 360 (pvlib: 180 is south)")
    if "timezone" in out.columns:
        zones = out["timezone"].dropna().astype(str)
        if (zones != TIMEZONE).any():
            raise ValueError(f"Only {TIMEZONE} is supported")
    return out.reset_index(drop=True)


def load_readings(path: Path) -> pd.DataFrame:
    if path.is_dir():
        files = sorted(item for item in path.glob("*.csv") if item.is_file())
        if not files:
            raise FileNotFoundError(f"No readings CSV in {path}")
        frames = [_read_readings_file(item) for item in files]
        out = pd.concat(frames, ignore_index=True)
    else:
        out = _read_readings_file(path)
    if out.empty:
        raise ValueError(f"{path} has no readings")
    if out.duplicated(["site_id", "timestamp"]).any():
        raise ValueError("Duplicate site_id and timestamp in readings")
    return out.sort_values(["site_id", "timestamp"]).reset_index(drop=True)


def _read_readings_file(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = [column for column in READING_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    out = pd.DataFrame(
        {
            "site_id": frame["site_id"].astype(str),
            "timestamp": to_colombo(frame["timestamp"]),
            "pv_kw": pd.to_numeric(frame["pv_kw"]),
        }
    )
    if (~np.isfinite(out["pv_kw"])).any() or (out["pv_kw"] < 0).any():
        raise ValueError(f"{path} has a missing or negative pv_kw")
    out["is_simulated"] = _flag_column(frame, "is_simulated")
    if "data_label" in frame.columns:
        out["data_label"] = frame["data_label"].astype(str)
    else:
        out["data_label"] = np.where(out["is_simulated"], "SIMULATED", "MEASURED")
    return out


def load_weather_table(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = [column for column in WEATHER_COLUMNS if column not in frame.columns]
    if missing or "timestamp" not in frame.columns:
        absent = missing if "timestamp" in frame.columns else ["timestamp", *missing]
        raise ValueError(f"{path} is missing columns: {', '.join(absent)}")
    out = pd.DataFrame({"timestamp": to_colombo(frame["timestamp"])})
    for column in WEATHER_COLUMNS:
        out[column] = pd.to_numeric(frame[column], errors="coerce")
    if "site_id" in frame.columns:
        out["site_id"] = frame["site_id"].astype(str)
    if "location_id" in frame.columns:
        out["location_id"] = frame["location_id"].astype(str)
    out["is_simulated"] = _flag_column(frame, "is_simulated")
    if "data_label" in frame.columns:
        out["data_label"] = frame["data_label"].astype(str)
    else:
        out["data_label"] = np.where(out["is_simulated"], "SIMULATED", "MEASURED")
    if "weather_kind" in frame.columns:
        out["weather_kind"] = frame["weather_kind"].astype(str)
    return out


def align_weather(weather: pd.DataFrame, sites: pd.DataFrame) -> pd.DataFrame:
    """Attach weather to homes.

    A file that already has `site_id` is used as-is. A city file from
    `data/pipeline` (it has `location_id` instead) is copied onto every site
    with that `location_id`.
    """
    if "site_id" in weather.columns and weather["site_id"].notna().any():
        return weather.copy()
    if "location_id" not in weather.columns or "location_id" not in sites.columns:
        raise ValueError(
            "Weather needs site_id, or both the weather file and the sites "
            "file need location_id."
        )
    homes = sites[["site_id", "location_id"]].copy()
    homes["location_id"] = homes["location_id"].astype(str)
    weather = weather.copy()
    weather["location_id"] = weather["location_id"].astype(str)
    merged = homes.merge(weather, on="location_id", how="inner")
    if merged.empty:
        raise ValueError("No weather rows matched a site location_id")
    return merged


def write_table(frame: pd.DataFrame, path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[column]):
            out[column] = [
                value.isoformat() if pd.notna(value) else ""
                for value in out[column]
            ]
    out.to_csv(path, index=False)
    path.with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _flag_column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame.columns:
        return pd.Series(False, index=frame.index)
    values = frame[name]
    if values.dtype == bool:
        return values.fillna(False)
    return values.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
