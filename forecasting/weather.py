"""Open-Meteo weather for one or more homes, cached as CSV.

`kind="forecast"` calls the forecast API. `kind="historical"` calls the
archive (reanalysis). The archive is not a day-ahead forecast. For training
against the forecast the live model will actually see, pass a
`open_meteo_previous_day1` file from `data/pipeline` instead. See `data/README.md`.

A second request for the same site, kind, resolution and dates reads the
cache and does not call the network.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from data.pipeline.config import OPEN_METEO_ATTRIBUTION
from data.pipeline.http_client import HttpClient
from data.pipeline.tables import date_chunks
from forecasting.config import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_FORECAST_URL,
    OPEN_METEO_TO_COLUMN,
    OPEN_METEO_VARIABLES,
    RESOLUTION_FREQ,
    TIMEZONE,
)
from forecasting.tables import load_weather_table, to_colombo, write_table


def fetch_weather(
    sites: pd.DataFrame,
    start: date,
    end: date,
    *,
    kind: str,
    resolution: str,
    cache_dir: Path,
    client: HttpClient | None = None,
) -> pd.DataFrame:
    if kind not in {"forecast", "historical"}:
        raise ValueError("kind must be 'forecast' or 'historical'")
    if resolution not in RESOLUTION_FREQ:
        raise ValueError(f"resolution must be one of {', '.join(RESOLUTION_FREQ)}")
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    if kind == "historical" and resolution == "15min":
        raise ValueError(
            "The Open-Meteo archive used here is hourly. "
            "Use hourly resolution, or kind=forecast for a 15-minute series."
        )
    if client is None:
        client = HttpClient(pause_s=1.0, max_retries=4, timeout_s=60)
    frames = [
        _one_site(site, start, end, kind=kind, resolution=resolution, cache_dir=cache_dir, client=client)
        for site in sites.itertuples(index=False)
    ]
    return pd.concat(frames, ignore_index=True)


def _one_site(site, start, end, *, kind, resolution, cache_dir, client) -> pd.DataFrame:
    path = (
        Path(cache_dir)
        / f"{site.site_id}_{kind}_{resolution}_{start.isoformat()}_{end.isoformat()}.csv"
    )
    if path.is_file():
        cached = load_weather_table(path)
        cached["site_id"] = str(site.site_id)
        return cached

    if kind == "historical":
        chunks = date_chunks(start, end, 120)
    else:
        chunks = [(start, end)]
    parts = [
        _request(
            client,
            kind=kind,
            resolution=resolution,
            latitude=float(site.latitude),
            longitude=float(site.longitude),
            site_id=str(site.site_id),
            start=chunk_start,
            end=chunk_end,
        )
        for chunk_start, chunk_end in chunks
    ]
    frame = pd.concat(parts, ignore_index=True)
    frame = frame.drop_duplicates(["site_id", "timestamp"], keep="last")
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    note = (
        "Open-Meteo forecast API. Radiation is the mean over the preceding interval."
        if kind == "forecast"
        else (
            "Open-Meteo archive (reanalysis), not a day-ahead forecast. "
            "Do not describe a model trained on this file as if it had only seen yesterday's forecast."
        )
    )
    write_table(
        frame,
        path,
        {
            "project": "Rooftops to Power Plant",
            "data_label": "MEASURED",
            "is_simulated": False,
            "controls_equipment": False,
            "source": "open_meteo_forecast" if kind == "forecast" else "open_meteo_archive",
            "kind": kind,
            "resolution": resolution,
            "timezone": TIMEZONE,
            "site_id": str(site.site_id),
            "latitude": float(site.latitude),
            "longitude": float(site.longitude),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "attribution": OPEN_METEO_ATTRIBUTION,
            "note": note,
            "rows": int(len(frame)),
        },
    )
    return frame


def _request(client, *, kind, resolution, latitude, longitude, site_id, start, end) -> pd.DataFrame:
    if kind == "forecast":
        url = OPEN_METEO_FORECAST_URL
        block = "minutely_15" if resolution == "15min" else "hourly"
    else:
        url = OPEN_METEO_ARCHIVE_URL
        block = "hourly"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        block: ",".join(OPEN_METEO_VARIABLES),
        "timezone": TIMEZONE,
        "timeformat": "iso8601",
    }
    payload = client.get_json(url, params)
    return _payload_to_frame(payload, block, site_id=site_id, kind=kind)


def _payload_to_frame(payload: dict, block: str, *, site_id: str, kind: str) -> pd.DataFrame:
    body = payload.get(block) or {}
    if "time" not in body:
        raise ValueError(f"Open-Meteo response has no {block} time: {str(payload)[:300]}")
    frame = pd.DataFrame({"timestamp": to_colombo(body["time"])})
    for api_name, column in OPEN_METEO_TO_COLUMN.items():
        if api_name not in body:
            raise ValueError(f"Open-Meteo response is missing {api_name}")
        frame[column] = pd.to_numeric(pd.Series(body[api_name]), errors="coerce")
    frame["site_id"] = site_id
    frame["is_simulated"] = False
    frame["data_label"] = "MEASURED"
    frame["weather_kind"] = "forecast" if kind == "forecast" else "archive"
    return frame
