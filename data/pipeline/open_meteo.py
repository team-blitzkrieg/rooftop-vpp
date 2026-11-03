"""Open-Meteo downloads: archive, historical forecast, previous-day-1, and live.

Radiation variables from Open-Meteo are the mean of the preceding hour.
Temperature, humidity, cloud cover and wind are the value at the timestamp.
That is how the API defines them. This module does not shift the columns.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd

from data.pipeline.config import (
    LIVE_CURRENT,
    LIVE_FORECAST_URL,
    OPEN_METEO_COLUMN,
    OPEN_METEO_HOURLY,
    TIMEZONE,
    Location,
    WeatherSource,
)
from data.pipeline.http_client import HttpClient
from data.pipeline.tables import date_chunks, order_weather


def fetch_open_meteo(
    source: WeatherSource,
    location: Location,
    start: date,
    end: date,
    client: HttpClient,
    *,
    model: str | None,
    chunk_days: int,
    retrieved_at: datetime | None = None,
) -> pd.DataFrame:
    if source.kind != "open_meteo":
        raise ValueError(f"{source.cli_name} is not an Open-Meteo source")
    retrieved_at = _as_utc(retrieved_at)
    names = [name + source.variable_suffix for name in OPEN_METEO_HOURLY]
    frames = []
    for chunk_start, chunk_end in date_chunks(start, end, chunk_days):
        print(
            f"  {source.source_id} {location.id} {chunk_start.isoformat()} "
            f"to {chunk_end.isoformat()}",
            flush=True,
        )
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start_date": chunk_start.isoformat(),
            "end_date": chunk_end.isoformat(),
            "hourly": ",".join(names),
            "timezone": TIMEZONE,
            "wind_speed_unit": "ms",
            "timeformat": "iso8601",
        }
        if model:
            params["models"] = model
        payload = client.get_json(source.endpoint, params)
        frames.append(
            hourly_payload_to_frame(
                payload,
                location=location,
                source=source,
                retrieved_at=retrieved_at,
                variable_suffix=source.variable_suffix,
            )
        )
    return order_weather(pd.concat(frames, ignore_index=True))


def fetch_live(
    location: Location,
    client: HttpClient,
    *,
    forecast_days: int = 7,
    retrieved_at: datetime | None = None,
) -> dict[str, pd.DataFrame]:
    """Current conditions, hourly forecast, and 15-minute forecast.

    Open-Meteo returns `forecast_days` local calendar days, starting at
    midnight in the requested timezone. With 7 that is today plus the next
    six days. Outside Europe and North America the 15-minute series is
    interpolated from hourly data. The columns still match the hourly file.
    """
    if forecast_days < 1 or forecast_days > 16:
        raise ValueError("forecast_days must be between 1 and 16")
    retrieved_at = _as_utc(retrieved_at)
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "timezone": TIMEZONE,
        "wind_speed_unit": "ms",
        "timeformat": "iso8601",
        "forecast_days": forecast_days,
        "current": ",".join(LIVE_CURRENT),
        "hourly": ",".join(OPEN_METEO_HOURLY),
        "minutely_15": ",".join(OPEN_METEO_HOURLY),
    }
    payload = client.get_json(LIVE_FORECAST_URL, params)
    return parse_live_payload(payload, location=location, retrieved_at=retrieved_at)


def parse_live_payload(
    payload: dict,
    *,
    location: Location,
    retrieved_at: datetime,
) -> dict[str, pd.DataFrame]:
    retrieved_at = _as_utc(retrieved_at)
    _check_units(payload.get("hourly_units") or {}, "")
    if payload.get("minutely_15_units"):
        _check_units(payload["minutely_15_units"], "")
    frames = {
        "hourly": _block_to_frame(
            payload["hourly"],
            location=location,
            payload=payload,
            source_id="open_meteo_forecast",
            data_kind="forecast",
            fixed_lead_hours=None,
            lead_from_clock=True,
            retrieved_at=retrieved_at,
            variable_suffix="",
        )
    }
    if payload.get("minutely_15") and payload["minutely_15"].get("time"):
        frames["minutely_15"] = _block_to_frame(
            payload["minutely_15"],
            location=location,
            payload=payload,
            source_id="open_meteo_forecast",
            data_kind="forecast",
            fixed_lead_hours=None,
            lead_from_clock=True,
            retrieved_at=retrieved_at,
            variable_suffix="",
        )
    frames["current"] = _current_to_frame(
        payload.get("current") or {},
        location=location,
        payload=payload,
        retrieved_at=retrieved_at,
    )
    return frames


def hourly_payload_to_frame(
    payload: dict,
    *,
    location: Location,
    source: WeatherSource,
    retrieved_at: datetime,
    variable_suffix: str,
) -> pd.DataFrame:
    if "hourly" not in payload:
        raise ValueError(
            f"Open-Meteo response for {location.id} has no hourly block: "
            f"{str(payload)[:400]}"
        )
    _check_units(payload.get("hourly_units") or {}, variable_suffix)
    return _block_to_frame(
        payload["hourly"],
        location=location,
        payload=payload,
        source_id=source.source_id,
        data_kind=source.data_kind,
        fixed_lead_hours=source.forecast_lead_hours,
        lead_from_clock=False,
        retrieved_at=retrieved_at,
        variable_suffix=variable_suffix,
    )


def _block_to_frame(
    block: dict,
    *,
    location: Location,
    payload: dict,
    source_id: str,
    data_kind: str,
    fixed_lead_hours: float | None,
    lead_from_clock: bool,
    retrieved_at: datetime,
    variable_suffix: str,
) -> pd.DataFrame:
    times = block.get("time") or []
    if not times:
        raise ValueError(f"Open-Meteo returned no timestamps for {location.id}")
    n = len(times)
    columns: dict[str, list] = {}
    for api_name, column in OPEN_METEO_COLUMN.items():
        key = api_name + variable_suffix
        values = block.get(key)
        if values is None:
            columns[column] = [pd.NA] * n
            continue
        if len(values) != n:
            raise ValueError(f"{key} has {len(values)} values, time has {n}")
        columns[column] = values

    frame = pd.DataFrame(columns)
    frame["timestamp"] = _localise(times)
    for column in OPEN_METEO_COLUMN.values():
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    _stamp_identity(
        frame,
        location=location,
        payload=payload,
        source_id=source_id,
        data_kind=data_kind,
        retrieved_at=retrieved_at,
    )
    if lead_from_clock:
        delta = frame["timestamp"].dt.tz_convert("UTC") - retrieved_at
        frame["forecast_lead_hours"] = delta.dt.total_seconds() / 3600.0
    elif fixed_lead_hours is None:
        # Reanalysis and the stitched historical-forecast series are not a
        # day-ahead forecast. Leave the lead blank so it is not mistaken for one.
        frame["forecast_lead_hours"] = pd.NA
    else:
        frame["forecast_lead_hours"] = float(fixed_lead_hours)
    return frame


def _current_to_frame(
    current: dict,
    *,
    location: Location,
    payload: dict,
    retrieved_at: datetime,
) -> pd.DataFrame:
    if "time" not in current:
        raise ValueError(f"Open-Meteo current block for {location.id} has no time")
    row = {column: pd.NA for column in OPEN_METEO_COLUMN.values()}
    for api_name, column in OPEN_METEO_COLUMN.items():
        if api_name in current:
            row[column] = current[api_name]
    frame = pd.DataFrame([row])
    frame["timestamp"] = _localise([current["time"]])
    for column in OPEN_METEO_COLUMN.values():
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    _stamp_identity(
        frame,
        location=location,
        payload=payload,
        source_id="open_meteo_forecast",
        data_kind="current",
        retrieved_at=retrieved_at,
    )
    delta = frame["timestamp"].dt.tz_convert("UTC") - retrieved_at
    frame["forecast_lead_hours"] = delta.dt.total_seconds() / 3600.0
    return frame


def _stamp_identity(
    frame: pd.DataFrame,
    *,
    location: Location,
    payload: dict,
    source_id: str,
    data_kind: str,
    retrieved_at: datetime,
) -> None:
    frame["location_id"] = location.id
    frame["latitude"] = location.latitude
    frame["longitude"] = location.longitude
    frame["grid_latitude"] = payload.get("latitude")
    frame["grid_longitude"] = payload.get("longitude")
    frame["grid_elevation_m"] = payload.get("elevation")
    frame["source"] = source_id
    frame["data_kind"] = data_kind
    frame["retrieved_at_utc"] = retrieved_at


def _localise(values) -> pd.Series:
    times = pd.to_datetime(pd.Series(values))
    if getattr(times.dt, "tz", None) is None:
        return times.dt.tz_localize(TIMEZONE)
    return times.dt.tz_convert(TIMEZONE)


def _check_units(hourly_units: dict, suffix: str) -> None:
    """Reject a response that is not in the units the rest of the code assumes."""

    def unit(name: str):
        return hourly_units.get(name + suffix)

    wind = unit("wind_speed_10m")
    if wind is not None and wind not in {"m/s", "ms"}:
        raise ValueError(
            f"Expected wind speed in m/s, Open-Meteo said {wind!r}. "
            "The client always sends wind_speed_unit=ms."
        )
    temp = unit("temperature_2m")
    if temp is not None and temp not in {"°C", "C", "celsius"}:
        raise ValueError(f"Expected temperature in °C, Open-Meteo said {temp!r}.")
    radiation = unit("shortwave_radiation")
    if radiation is not None and radiation.replace(" ", "") not in {"W/m²", "W/m2", "W/m^2"}:
        raise ValueError(f"Expected radiation in W/m², Open-Meteo said {radiation!r}.")
    precip = unit("precipitation")
    if precip is not None and precip not in {"mm", "millimeter"}:
        raise ValueError(f"Expected precipitation in mm, Open-Meteo said {precip!r}.")


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def open_meteo_meta(source: WeatherSource, *, model: str | None, start: date, end: date) -> dict:
    attribution = source.attribution
    if model == "era5":
        from data.pipeline.config import ERA5_ATTRIBUTION

        attribution = f"{attribution} {ERA5_ATTRIBUTION}"
    return {
        "project": "Rooftops to Power Plant",
        "source": source.source_id,
        "data_kind": source.data_kind,
        "description": source.description,
        "endpoint": source.endpoint,
        "model": model,
        "timezone": TIMEZONE,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "forecast_lead_hours": source.forecast_lead_hours,
        "radiation_note": (
            "Open-Meteo shortwave, direct, diffuse and direct-normal values "
            "are the mean of the preceding hour. Temperature, humidity, cloud "
            "cover and wind are the value at the timestamp."
        ),
        "pv_is_simulated": False,
        "licence": source.licence_name,
        "licence_url": source.licence_url,
        "attribution": attribution,
    }


__all__ = [
    "fetch_live",
    "fetch_open_meteo",
    "hourly_payload_to_frame",
    "open_meteo_meta",
    "parse_live_payload",
]
