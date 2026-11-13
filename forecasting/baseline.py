"""Physics baseline: plane-of-array irradiance times size times a loss factor.

Night is zero because the sun is below the horizon, including when the weather
file still carries irradiance. The result is clipped to the AC nameplate.
`loss_factor` is a constant, not a coefficient fitted on the test set.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib
from pvlib import irradiance
from pvlib import location as pvlocation

from forecasting.config import BASELINE_ALBEDO, BASELINE_LOSS_FACTOR, TIMEZONE


def solar_position(
    timestamps: pd.DatetimeIndex,
    latitude: float,
    longitude: float,
) -> pd.DataFrame:
    index = pd.DatetimeIndex(timestamps)
    if index.tz is None:
        index = index.tz_localize(TIMEZONE)
    else:
        index = index.tz_convert(TIMEZONE)
    site = pvlocation.Location(
        float(latitude),
        float(longitude),
        tz=TIMEZONE,
        altitude=10.0,
    )
    position = site.get_solarposition(index)
    return pd.DataFrame(
        {
            "solar_zenith_deg": position["apparent_zenith"].to_numpy(dtype=float),
            "solar_azimuth_deg": position["azimuth"].to_numpy(dtype=float),
            "solar_elevation_deg": position["apparent_elevation"].to_numpy(dtype=float),
        }
    )


def poa_irradiance(
    zenith_deg,
    azimuth_deg,
    tilt_deg: float,
    surface_azimuth_deg: float,
    ghi_wm2,
    dni_wm2,
    dhi_wm2,
) -> np.ndarray:
    """Isotropic plane-of-array irradiance, W/m². Missing weather stays missing."""
    ghi = np.asarray(ghi_wm2, dtype=float)
    dni = np.asarray(dni_wm2, dtype=float)
    dhi = np.asarray(dhi_wm2, dtype=float)
    missing = ~np.isfinite(ghi) | ~np.isfinite(dni) | ~np.isfinite(dhi)
    poa = irradiance.get_total_irradiance(
        surface_tilt=float(tilt_deg),
        surface_azimuth=float(surface_azimuth_deg),
        solar_zenith=np.asarray(zenith_deg, dtype=float),
        solar_azimuth=np.asarray(azimuth_deg, dtype=float),
        dni=np.where(missing, 0.0, dni),
        ghi=np.where(missing, 0.0, ghi),
        dhi=np.where(missing, 0.0, dhi),
        albedo=BASELINE_ALBEDO,
        model="isotropic",
    )
    values = np.clip(np.asarray(poa["poa_global"], dtype=float), 0, None)
    return np.where(missing, np.nan, values)


def baseline_kw(
    timestamps,
    *,
    latitude: float,
    longitude: float,
    tilt_deg: float,
    azimuth_deg: float,
    system_kw: float,
    ghi_wm2,
    dni_wm2,
    dhi_wm2,
    loss_factor: float = BASELINE_LOSS_FACTOR,
) -> np.ndarray:
    """AC kW from forecast irradiance. Zero at night, never above `system_kw`."""
    if loss_factor < 0:
        raise ValueError(f"loss_factor must be >= 0, got {loss_factor}")
    nameplate = float(system_kw)
    if nameplate <= 0:
        raise ValueError(f"system_kw must be positive, got {system_kw}")
    position = solar_position(pd.DatetimeIndex(timestamps), latitude, longitude)
    poa = poa_irradiance(
        position["solar_zenith_deg"],
        position["solar_azimuth_deg"],
        tilt_deg,
        azimuth_deg,
        ghi_wm2,
        dni_wm2,
        dhi_wm2,
    )
    raw = poa / 1000.0 * nameplate * float(loss_factor)
    raw = np.where(np.isfinite(raw), np.clip(raw, 0.0, nameplate), np.nan)
    night = position["solar_elevation_deg"].to_numpy(dtype=float) <= 0.0
    return np.where(night, 0.0, raw)


def baseline_power(
    frame: pd.DataFrame,
    loss_factor: float = BASELINE_LOSS_FACTOR,
) -> pd.Series:
    """`baseline_kw` on each row, using that row's site geometry and weather."""
    values = pd.Series(np.nan, index=frame.index, dtype=float)
    for _, group in frame.groupby("site_id", sort=False):
        values.loc[group.index] = baseline_kw(
            group["timestamp"],
            latitude=float(group["latitude"].iloc[0]),
            longitude=float(group["longitude"].iloc[0]),
            tilt_deg=float(group["tilt_deg"].iloc[0]),
            azimuth_deg=float(group["azimuth_deg"].iloc[0]),
            system_kw=float(group["system_kw"].iloc[0]),
            ghi_wm2=group["ghi_wm2"],
            dni_wm2=group["dni_wm2"],
            dhi_wm2=group["dhi_wm2"],
            loss_factor=loss_factor,
        )
    return values


def library_versions() -> dict[str, str]:
    import numpy
    import pandas

    return {
        "pvlib": pvlib.__version__,
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
    }
