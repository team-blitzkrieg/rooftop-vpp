"""Turn hourly weather into simulated AC output for a rooftop array.

The result is a model, not a meter reading. Column names end in `_simulated`
and `is_simulated` is always true. Nothing here is fitted to a Sri Lankan
inverter log.

Steps, all from pvlib:

1. Sun position at the location.
2. Plane-of-array irradiance, isotropic sky, albedo 0.2.
3. Cell temperature with the SAPM close-mount glass/glass coefficients
   shipped with pvlib (a rooftop-style mount, warmer than an open rack).
4. DC power with the PVWatts model. The temperature coefficient is the
   PVWatts crystalline-silicon default, -0.004 per degree C from 25 C.
5. AC power with the PVWatts inverter model. The AC cap is the configured
   system size. The DC array at standard test conditions is set equal to
   that same size, a simple 1:1 assumption.

`azimuth_deg` uses the pvlib convention: 180 is due south, 90 is east.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pvlib
from pvlib import irradiance, inverter, location as pvlocation, pvsystem, temperature

from data.pipeline.config import (
    DEFAULT_ALBEDO,
    DEFAULT_AZIMUTH_DEG,
    DEFAULT_ETA_INV,
    DEFAULT_GAMMA_PDC,
    DEFAULT_SYSTEM_SIZES_KW,
    DEFAULT_TILT_DEG,
    PV_COLUMNS,
    TEMP_REF_C,
    TIMEZONE,
)

REQUIRED_WEATHER = [
    "timestamp",
    "location_id",
    "latitude",
    "longitude",
    "ghi_wm2",
    "dni_wm2",
    "dhi_wm2",
    "temp_c",
    "wind_speed_ms",
    "source",
    "data_kind",
]

WEATHER_FEATURES = [
    "temp_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "cloud_cover_pct",
    "wind_speed_ms",
    "ghi_wm2",
    "dni_wm2",
    "dhi_wm2",
]


def sapm_close_mount() -> dict:
    return dict(temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["close_mount_glass_glass"])


def simulate_pv(
    weather: pd.DataFrame,
    *,
    sizes_kw: tuple[float, ...] = DEFAULT_SYSTEM_SIZES_KW,
    tilt_deg: float = DEFAULT_TILT_DEG,
    azimuth_deg: float = DEFAULT_AZIMUTH_DEG,
    albedo: float = DEFAULT_ALBEDO,
    gamma_pdc: float = DEFAULT_GAMMA_PDC,
    eta_inv_nom: float = DEFAULT_ETA_INV,
) -> pd.DataFrame:
    missing = [column for column in REQUIRED_WEATHER if column not in weather.columns]
    if missing:
        raise ValueError(f"Weather table is missing columns: {', '.join(missing)}")
    if not sizes_kw:
        raise ValueError("Pass at least one system size in kW")

    pieces = []
    for location_id, group in weather.groupby("location_id", sort=False):
        pieces.append(
            _simulate_location(
                group,
                location_id=str(location_id),
                sizes_kw=sizes_kw,
                tilt_deg=tilt_deg,
                azimuth_deg=azimuth_deg,
                albedo=albedo,
                gamma_pdc=gamma_pdc,
                eta_inv_nom=eta_inv_nom,
            )
        )
    out = pd.concat(pieces, ignore_index=True)
    out = out.sort_values(["location_id", "system_kw", "timestamp"]).reset_index(drop=True)
    return out[PV_COLUMNS]


def _simulate_location(
    weather: pd.DataFrame,
    *,
    location_id: str,
    sizes_kw: tuple[float, ...],
    tilt_deg: float,
    azimuth_deg: float,
    albedo: float,
    gamma_pdc: float,
    eta_inv_nom: float,
) -> pd.DataFrame:
    frame = weather.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    frame = frame.reset_index(drop=True)
    timestamps = pd.DatetimeIndex(frame["timestamp"])
    if timestamps.tz is None:
        timestamps = timestamps.tz_localize(TIMEZONE)
    else:
        timestamps = timestamps.tz_convert(TIMEZONE)

    latitude = float(frame["latitude"].iloc[0])
    longitude = float(frame["longitude"].iloc[0])
    altitude = 0.0
    if "grid_elevation_m" in frame.columns and pd.notna(frame["grid_elevation_m"].iloc[0]):
        altitude = float(frame["grid_elevation_m"].iloc[0])

    site = pvlocation.Location(
        latitude,
        longitude,
        tz=TIMEZONE,
        altitude=altitude,
        name=location_id,
    )
    solpos = site.get_solarposition(timestamps)

    ghi = frame["ghi_wm2"].to_numpy(dtype=float)
    dni = frame["dni_wm2"].to_numpy(dtype=float)
    dhi = frame["dhi_wm2"].to_numpy(dtype=float)
    temp_air = frame["temp_c"].to_numpy(dtype=float)
    wind = frame["wind_speed_ms"].to_numpy(dtype=float)
    radiation_missing = ~np.isfinite(ghi) | ~np.isfinite(dni) | ~np.isfinite(dhi)
    weather_missing = radiation_missing | ~np.isfinite(temp_air) | ~np.isfinite(wind)

    poa = irradiance.get_total_irradiance(
        surface_tilt=tilt_deg,
        surface_azimuth=azimuth_deg,
        solar_zenith=solpos["apparent_zenith"].to_numpy(dtype=float),
        solar_azimuth=solpos["azimuth"].to_numpy(dtype=float),
        dni=np.where(radiation_missing, 0.0, dni),
        ghi=np.where(radiation_missing, 0.0, ghi),
        dhi=np.where(radiation_missing, 0.0, dhi),
        albedo=albedo,
        model="isotropic",
    )
    poa_global = np.clip(np.asarray(poa["poa_global"], dtype=float), 0, None)
    poa_global = np.where(radiation_missing, np.nan, poa_global)

    coeff = sapm_close_mount()
    cell_temp = np.asarray(
        temperature.sapm_cell(
            poa_global,
            temp_air,
            wind,
            coeff["a"],
            coeff["b"],
            coeff["deltaT"],
        ),
        dtype=float,
    )
    cell_temp = np.where(weather_missing, np.nan, cell_temp)

    features = {}
    for column in WEATHER_FEATURES:
        if column in frame.columns:
            features[column] = frame[column].to_numpy()
        else:
            features[column] = np.full(len(frame), np.nan)

    pieces = []
    for size_kw in sizes_kw:
        pdc0_w = float(size_kw) * 1000.0
        # PVWatts inverter: AC cap = eta_inv_nom * pdc0_argument.
        # Pass pdc0_argument = nameplate / eta so the cap equals the size.
        dc_w = np.asarray(
            pvsystem.pvwatts_dc(
                poa_global,
                cell_temp,
                pdc0_w,
                gamma_pdc,
                temp_ref=TEMP_REF_C,
            ),
            dtype=float,
        )
        ac_w = np.asarray(
            inverter.pvwatts(
                dc_w,
                pdc0_w / eta_inv_nom,
                eta_inv_nom=eta_inv_nom,
            ),
            dtype=float,
        )
        dc_kw = np.where(np.isfinite(dc_w), np.clip(dc_w / 1000.0, 0, None), np.nan)
        ac_kw = np.where(np.isfinite(ac_w), np.clip(ac_w / 1000.0, 0, size_kw), np.nan)

        piece = pd.DataFrame(
            {
                "timestamp": pd.Series(timestamps).reset_index(drop=True),
                "location_id": location_id,
                "latitude": latitude,
                "longitude": longitude,
                "weather_source": frame["source"].iloc[0],
                "weather_data_kind": frame["data_kind"].iloc[0],
                "system_kw": float(size_kw),
                "tilt_deg": float(tilt_deg),
                "azimuth_deg": float(azimuth_deg),
                "inverter_ac_limit_kw": float(size_kw),
                "poa_global_wm2_simulated": np.round(poa_global, 2),
                "cell_temp_c_simulated": np.round(cell_temp, 2),
                "pv_dc_kw_simulated": np.round(dc_kw, 4),
                "pv_ac_kw_simulated": np.round(ac_kw, 4),
                "is_simulated": True,
                **features,
            }
        )
        pieces.append(piece)
    return pd.concat(pieces, ignore_index=True)


def pv_meta(
    *,
    weather_source: str,
    weather_data_kind: str,
    sizes_kw: tuple[float, ...],
    tilt_deg: float,
    azimuth_deg: float,
    albedo: float,
    gamma_pdc: float,
    eta_inv_nom: float,
    weather_path: str | None = None,
) -> dict:
    coeff = sapm_close_mount()
    return {
        "project": "Rooftops to Power Plant",
        "pv_is_simulated": True,
        "is_measured_generation": False,
        "note": (
            "Hourly AC output from a pvlib model of a generic rooftop array. "
            "Not measured inverter data, and not a statistic of Sri Lankan roofs."
        ),
        "weather_source": weather_source,
        "weather_data_kind": weather_data_kind,
        "weather_file": weather_path,
        "system_sizes_kw": list(sizes_kw),
        "timezone": TIMEZONE,
        "model": {
            "library": "pvlib",
            "library_version": pvlib.__version__,
            "library_url": "https://pvlib-python.readthedocs.io/",
            "library_licence": "BSD-3-Clause",
            "transposition": "isotropic",
            "albedo": albedo,
            "dc_model": "pvwatts",
            "temperature_model": "sapm",
            "temperature_parameter_set": "close_mount_glass_glass",
            "temperature_coefficients": coeff,
            "gamma_pdc_per_c": gamma_pdc,
            "temp_ref_c": TEMP_REF_C,
            "ac_model": "pvwatts inverter",
            "eta_inv_nom": eta_inv_nom,
            "array_stc_kw_equals_ac_nameplate": True,
            "tilt_deg": tilt_deg,
            "azimuth_deg": azimuth_deg,
            "azimuth_convention": "pvlib: 180 is due south, 90 is east, 0 is north",
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
