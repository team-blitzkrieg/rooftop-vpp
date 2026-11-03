"""NASA POWER hourly point data.

Timestamps in the API are the start of the hour. We ask for UTC and convert
to Asia/Colombo, so the clock time falls on the half hour (UTC+5:30). That
is not lined up with Open-Meteo, which labels hours on the Colombo clock.
The forecasting code should resample before joining the two.

The missing-data fill value (usually -999) is turned into a blank. A real
zero, such as irradiance at night, is kept.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd

from data.pipeline.config import (
    NASA_COLUMN,
    NASA_PARAMETERS,
    NASA_POWER_ATTRIBUTION,
    NASA_UNITS,
    TIMEZONE,
    Location,
    WeatherSource,
)
from data.pipeline.http_client import HttpClient
from data.pipeline.tables import clip_to_local_days, date_chunks, order_weather


def fetch_nasa_power(
    source: WeatherSource,
    location: Location,
    start: date,
    end: date,
    client: HttpClient,
    *,
    chunk_days: int,
    retrieved_at: datetime | None = None,
) -> pd.DataFrame:
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc)
    elif retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
    else:
        retrieved_at = retrieved_at.astimezone(timezone.utc)

    # NASA dates are UTC days. Colombo is UTC+5:30, so the first half-hour of
    # a local day sits on the previous UTC date. Ask for that extra day, then
    # drop anything outside the local dates the caller asked for.
    utc_start = start - timedelta(days=1)
    frames = []
    for chunk_start, chunk_end in date_chunks(utc_start, end, chunk_days):
        print(
            f"  {source.source_id} {location.id} {chunk_start.isoformat()} "
            f"to {chunk_end.isoformat()} (UTC days)",
            flush=True,
        )
        params = {
            "parameters": ",".join(NASA_PARAMETERS),
            "community": "RE",
            "longitude": location.longitude,
            "latitude": location.latitude,
            "start": chunk_start.strftime("%Y%m%d"),
            "end": chunk_end.strftime("%Y%m%d"),
            "format": "JSON",
            "time-standard": "UTC",
        }
        payload = client.get_json(source.endpoint, params)
        frames.append(
            nasa_payload_to_frame(
                payload,
                location=location,
                retrieved_at=retrieved_at,
            )
        )
    combined = order_weather(pd.concat(frames, ignore_index=True))
    return clip_to_local_days(combined, start, end)


def nasa_payload_to_frame(
    payload: dict,
    *,
    location: Location,
    retrieved_at: datetime,
) -> pd.DataFrame:
    properties = payload.get("properties") or {}
    parameters = properties.get("parameter")
    if not parameters:
        raise ValueError(
            "NASA POWER response did not contain properties.parameter: "
            f"{str(payload)[:500]}"
        )
    header = payload.get("header") or {}
    standard = str(header.get("time_standard", "")).upper()
    if standard and standard != "UTC":
        raise ValueError(f"Expected NASA POWER time standard UTC, got {standard!r}")
    fill = float(header.get("fill_value", -999))

    stamps = None
    for name in NASA_PARAMETERS:
        if name in parameters:
            stamps = list(parameters[name].keys())
            break
    if not stamps:
        raise ValueError(f"NASA POWER returned no hourly values for {location.id}")

    timestamps = pd.to_datetime(stamps, format="%Y%m%d%H", utc=True).tz_convert(TIMEZONE)
    frame = pd.DataFrame({"timestamp": timestamps})
    for api_name, column in NASA_COLUMN.items():
        series_map = parameters.get(api_name) or {}
        values = [series_map.get(stamp) for stamp in stamps]
        numeric = pd.to_numeric(pd.Series(values), errors="coerce")
        frame[column] = numeric.mask(numeric == fill)
    frame["direct_horizontal_wm2"] = pd.NA

    geometry = (payload.get("geometry") or {}).get("coordinates") or []
    grid_lon = geometry[0] if len(geometry) > 0 else pd.NA
    grid_lat = geometry[1] if len(geometry) > 1 else pd.NA
    grid_elev = geometry[2] if len(geometry) > 2 else pd.NA

    frame["location_id"] = location.id
    frame["latitude"] = location.latitude
    frame["longitude"] = location.longitude
    frame["grid_latitude"] = grid_lat
    frame["grid_longitude"] = grid_lon
    frame["grid_elevation_m"] = grid_elev
    frame["source"] = "nasa_power"
    frame["data_kind"] = "satellite_model"
    frame["forecast_lead_hours"] = pd.NA
    frame["retrieved_at_utc"] = retrieved_at
    return frame


def nasa_meta(source: WeatherSource, *, start: date, end: date, payload_header: dict | None = None) -> dict:
    return {
        "project": "Rooftops to Power Plant",
        "source": source.source_id,
        "data_kind": source.data_kind,
        "description": source.description,
        "endpoint": source.endpoint,
        "community": "RE",
        "time_standard": "UTC",
        "timezone": TIMEZONE,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "parameters": NASA_PARAMETERS,
        "units": NASA_UNITS,
        "time_note": (
            "NASA POWER timestamps are the start of the UTC hour, converted "
            "to Asia/Colombo, so they fall on the half hour (00:30, 01:30, "
            "and so on). The download asks for one extra UTC day at the start "
            "and then keeps only the Asia/Colombo dates requested, so the "
            "file starts at 00:30 on --start and ends at 23:30 on --end. "
            "Open-Meteo hours are labelled on the Colombo clock. Do not join "
            "the two on timestamp without resampling. Irradiance is Wh/m^2 "
            "for the hour, which is the same number as average W/m^2, and is "
            "stored as-is."
        ),
        "api_header": payload_header,
        "pv_is_simulated": False,
        "licence": source.licence_name,
        "licence_url": source.licence_url,
        "attribution": NASA_POWER_ATTRIBUTION,
    }
