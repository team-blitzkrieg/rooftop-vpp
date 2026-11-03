"""CSV read and write, date chunks, and the month slice used for samples."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from data.pipeline.config import TIMEZONE, WEATHER_COLUMNS


def parse_date(text: str) -> date:
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Date must be YYYY-MM-DD, got {text!r}") from exc


def date_chunks(start: date, end: date, chunk_days: int) -> list[tuple[date, date]]:
    """Inclusive date chunks. The pieces cover start through end and do not overlap."""
    if chunk_days < 1:
        raise ValueError(f"chunk_days must be at least 1, got {chunk_days}")
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    chunks: list[tuple[date, date]] = []
    cursor = start
    step = timedelta(days=chunk_days - 1)
    one_day = timedelta(days=1)
    while cursor <= end:
        chunk_end = min(end, cursor + step)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + one_day
    return chunks


def order_weather(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in WEATHER_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA
    out = out[WEATHER_COLUMNS]
    out = out.sort_values("timestamp")
    out = out.drop_duplicates(subset=["timestamp", "location_id"], keep="last")
    return out.reset_index(drop=True)


def write_dataset(frame: pd.DataFrame, csv_path: Path, meta: dict) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    for column in ("timestamp", "retrieved_at_utc"):
        if column in out.columns and pd.api.types.is_datetime64_any_dtype(out[column]):
            out[column] = [
                value.isoformat() if pd.notna(value) else ""
                for value in out[column]
            ]
    out.to_csv(csv_path, index=False, na_rep="")
    meta_path = csv_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, default=str) + "\n", encoding="utf-8")


def read_weather_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, keep_default_na=True)
    if "timestamp" not in frame.columns:
        raise ValueError(f"{path} has no timestamp column")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(TIMEZONE)
    if "retrieved_at_utc" in frame.columns:
        frame["retrieved_at_utc"] = pd.to_datetime(frame["retrieved_at_utc"], utc=True)
    numeric = [
        "latitude",
        "longitude",
        "grid_latitude",
        "grid_longitude",
        "grid_elevation_m",
        "forecast_lead_hours",
        "temp_c",
        "relative_humidity_pct",
        "precipitation_mm",
        "cloud_cover_pct",
        "wind_speed_ms",
        "ghi_wm2",
        "dni_wm2",
        "dhi_wm2",
        "direct_horizontal_wm2",
    ]
    for column in numeric:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def clip_to_local_days(frame: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Keep rows whose Asia/Colombo timestamp falls on start..end inclusive.

    `end` is the last calendar day, not an exclusive bound. The next midnight
    is excluded, so the last hour of `end` stays and the next day does not.
    """
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    start_ts = pd.Timestamp(year=start.year, month=start.month, day=start.day, tz=TIMEZONE)
    end_excl = pd.Timestamp(year=end.year, month=end.month, day=end.day, tz=TIMEZONE) + pd.Timedelta(days=1)
    timestamps = frame["timestamp"]
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize(TIMEZONE)
    else:
        timestamps = timestamps.dt.tz_convert(TIMEZONE)
    mask = (timestamps >= start_ts) & (timestamps < end_excl)
    return frame.loc[mask].reset_index(drop=True)


def slice_month(frame: pd.DataFrame, location_id: str, month: str) -> pd.DataFrame:
    """Rows for one location in a calendar month, Asia/Colombo.

    `month` is YYYY-MM. The end bound is the first instant of the next month,
    so the last hour of a 31-day month is kept and the next month is not.
    """
    year_text, month_text = month.split("-")
    year = int(year_text)
    month_number = int(month_text)
    if not 1 <= month_number <= 12:
        raise ValueError(f"Month must be YYYY-MM, got {month!r}")
    start = pd.Timestamp(year=year, month=month_number, day=1, tz=TIMEZONE)
    if month_number == 12:
        end = pd.Timestamp(year=year + 1, month=1, day=1, tz=TIMEZONE)
    else:
        end = pd.Timestamp(year=year, month=month_number + 1, day=1, tz=TIMEZONE)
    timestamps = frame["timestamp"]
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize(TIMEZONE)
    else:
        timestamps = timestamps.dt.tz_convert(TIMEZONE)
    mask = (frame["location_id"] == location_id) & (timestamps >= start) & (timestamps < end)
    return frame.loc[mask].copy()
