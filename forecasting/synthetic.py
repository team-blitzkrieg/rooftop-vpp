"""SIMULATED rooftop readings, for when the pilot logs are not in the repo.

Every row is labelled SIMULATED. The AC power is pvlib clear-sky irradiance
times one cloud factor, then a temperature loss, then noise. It is not a
meter reading and it is not the physics baseline (that baseline uses a
different loss and does not see this noise).

The weather written beside the readings is a noisy copy of the weather that
drove the power. That copy is what the model and the baseline are allowed
to see. The exact driving weather is not saved.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
import pvlib
from pvlib import location as pvlocation

from forecasting.baseline import poa_irradiance, solar_position
from forecasting.config import (
    EXAMPLE_SITES,
    RESOLUTION_FREQ,
    SYNTHETIC_LOSS_FACTOR,
    SYNTHETIC_TEMP_COEFF,
    SYNTHETIC_TEMP_REF_C,
    TIMEZONE,
)
from forecasting.tables import load_sites


def default_sites() -> pd.DataFrame:
    return load_sites(EXAMPLE_SITES)


def generate_simulated(
    sites: pd.DataFrame,
    start: date,
    end: date,
    resolution: str,
    *,
    seed: int = 7,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if resolution not in RESOLUTION_FREQ:
        raise ValueError(f"resolution must be one of {', '.join(RESOLUTION_FREQ)}")
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    index = _index(start, end, resolution)
    rng = np.random.default_rng(seed)
    readings_parts = []
    weather_parts = []
    ordered = sites.sort_values("site_id")
    for site in ordered.itertuples(index=False):
        reading, weather = _one_site(site, index, rng)
        readings_parts.append(reading)
        weather_parts.append(weather)
    readings = pd.concat(readings_parts, ignore_index=True)
    weather = pd.concat(weather_parts, ignore_index=True)
    return readings, weather


def _index(start: date, end: date, resolution: str) -> pd.DatetimeIndex:
    start_ts = pd.Timestamp(datetime(start.year, start.month, start.day), tz=TIMEZONE)
    end_ts = pd.Timestamp(datetime(end.year, end.month, end.day), tz=TIMEZONE) + pd.Timedelta(days=1)
    return pd.date_range(
        start_ts,
        end_ts,
        freq=RESOLUTION_FREQ[resolution],
        inclusive="left",
    )


def _one_site(site, index: pd.DatetimeIndex, rng: np.random.Generator):
    latitude = float(site.latitude)
    longitude = float(site.longitude)
    system_kw = float(site.system_kw)
    location = pvlocation.Location(latitude, longitude, tz=TIMEZONE, altitude=10.0)
    clear = location.get_clearsky(index, model="ineichen")
    local = index.tz_convert(TIMEZONE)
    hour = local.hour.to_numpy(dtype=float) + local.minute.to_numpy(dtype=float) / 60.0
    day_code, _ = pd.factorize(local.normalize(), sort=True)
    n_days = int(day_code.max()) + 1
    daily = rng.uniform(8.0, 35.0, size=n_days)
    cloudy = rng.random(n_days) < 0.35
    n_cloudy = int(cloudy.sum())
    if n_cloudy:
        daily[cloudy] = rng.uniform(68.0, 95.0, size=n_cloudy)
    cloud = daily[day_code] + 8.0 * np.sin((hour - 5.0) / 24.0 * 2.0 * np.pi)
    cloud = np.clip(cloud + rng.normal(0.0, 3.0, size=len(index)), 0.0, 100.0)
    # One factor on every clear-sky component, as a stand-in for cloud.
    factor = 1.0 - 0.85 * (cloud / 100.0)
    ghi = clear["ghi"].to_numpy(dtype=float) * factor
    dni = clear["dni"].to_numpy(dtype=float) * factor
    dhi = clear["dhi"].to_numpy(dtype=float) * factor
    temp = 27.2 + 3.2 * np.sin((hour - 9.0) / 24.0 * 2.0 * np.pi)
    temp = temp + rng.normal(0.0, 0.3, size=len(index))

    position = solar_position(index, latitude, longitude)
    poa = poa_irradiance(
        position["solar_zenith_deg"],
        position["solar_azimuth_deg"],
        float(site.tilt_deg),
        float(site.azimuth_deg),
        ghi,
        dni,
        dhi,
    )
    temp_factor = 1.0 + SYNTHETIC_TEMP_COEFF * (temp - SYNTHETIC_TEMP_REF_C)
    power = poa / 1000.0 * system_kw * SYNTHETIC_LOSS_FACTOR * temp_factor
    day = position["solar_elevation_deg"].to_numpy(dtype=float) > 0.0
    power = power + np.where(day, rng.normal(0.0, 0.02 * system_kw, size=len(index)), 0.0)
    power = np.where(np.isfinite(power), np.clip(power, 0.0, system_kw), 0.0)
    power = np.where(day, power, 0.0)
    power = np.round(power, 4)

    # What a forecast issued for this window would have said. Not the series above.
    ghi_fc = np.round(np.clip(ghi * rng.normal(1.0, 0.06, size=len(index)), 0.0, None), 2)
    dni_fc = np.round(np.clip(dni * rng.normal(1.0, 0.08, size=len(index)), 0.0, None), 2)
    dhi_fc = np.round(np.clip(dhi * rng.normal(1.0, 0.08, size=len(index)), 0.0, None), 2)
    cloud_fc = np.round(np.clip(cloud + rng.normal(0.0, 6.0, size=len(index)), 0.0, 100.0), 2)
    temp_fc = np.round(temp + rng.normal(0.0, 0.6, size=len(index)), 2)

    site_id = str(site.site_id)
    readings = pd.DataFrame(
        {
            "site_id": site_id,
            "timestamp": index,
            "pv_kw": power,
            "is_simulated": True,
            "data_label": "SIMULATED",
        }
    )
    weather = pd.DataFrame(
        {
            "site_id": site_id,
            "timestamp": index,
            "ghi_wm2": ghi_fc,
            "dni_wm2": dni_fc,
            "dhi_wm2": dhi_fc,
            "cloud_cover_pct": cloud_fc,
            "temp_c": temp_fc,
            "is_simulated": True,
            "data_label": "SIMULATED",
            "weather_kind": "forecast",
        }
    )
    return readings, weather
