"""Locations, column names, and the weather sources this pipeline knows.

Coordinates are approximate city centres, used only as the point we send to
the weather APIs. They are not surveyed rooftops.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

TIMEZONE = "Asia/Colombo"
DEFAULT_START = "2020-01-01"

# Modelling choices for a generic crystalline-silicon rooftop, not a survey
# of installed systems. Sri Lanka sits at about 6°N to 10°N, so a fixed tilt
# of 10° and a south-facing azimuth (180° in the pvlib convention) is a
# simple year-round setting. Sizes are the AC nameplate in kW.
DEFAULT_SYSTEM_SIZES_KW = (3.0, 5.0, 10.0)
DEFAULT_TILT_DEG = 10.0
DEFAULT_AZIMUTH_DEG = 180.0
DEFAULT_ALBEDO = 0.20
DEFAULT_GAMMA_PDC = -0.004
DEFAULT_ETA_INV = 0.96
TEMP_REF_C = 25.0

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_WEATHER_DIR = REPO_ROOT / "data" / "raw" / "weather"
RAW_LIVE_DIR = REPO_ROOT / "data" / "raw" / "live"
PROCESSED_PV_DIR = REPO_ROOT / "data" / "processed" / "pv_simulated"
SAMPLE_DIR = REPO_ROOT / "data" / "sample"

USER_AGENT = "rooftop-vpp-data-pipeline/1.0 (educational; AIconomy 2026)"

OPEN_METEO_LICENCE_NAME = "CC BY 4.0"
OPEN_METEO_LICENCE_URL = "https://open-meteo.com/en/licence"
OPEN_METEO_ATTRIBUTION = (
    "Weather data by Open-Meteo.com, licensed CC BY 4.0 "
    f"({OPEN_METEO_LICENCE_URL})."
)
ERA5_ATTRIBUTION = (
    "Requested with models=era5. ERA5 is produced by ECMWF for the "
    "Copernicus Climate Change Service and is also under CC BY 4.0."
)

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"
NASA_POWER_HOME = "https://power.larc.nasa.gov/"
NASA_POWER_ATTRIBUTION = (
    "These data were obtained from the NASA Langley Research Center (LaRC) "
    "POWER Project funded through the NASA Earth Science/Applied Science "
    "Program."
)

# Hourly NASA POWER irradiance is published as Wh/m^2 for that hour, which is
# the same number as the average W/m^2. pvlib wants W/m^2, so the values are
# used as returned. See the data README.
NASA_UNITS = {
    "T2M": "deg C",
    "RH2M": "percent",
    "PRECTOTCORR": "mm per hour",
    "WS10M": "m/s",
    "CLOUD_AMT": "percent",
    "ALLSKY_SFC_SW_DWN": "Wh/m^2 over the hour (numerically equal to average W/m^2)",
    "ALLSKY_SFC_SW_DNI": "Wh/m^2 over the hour (numerically equal to average W/m^2)",
    "ALLSKY_SFC_SW_DIFF": "Wh/m^2 over the hour (numerically equal to average W/m^2)",
}


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    latitude: float
    longitude: float


LOCATIONS: dict[str, Location] = {
    "colombo": Location("colombo", "Colombo", 6.9271, 79.8612),
    "kandy": Location("kandy", "Kandy", 7.2906, 80.6337),
    "jaffna": Location("jaffna", "Jaffna", 9.6615, 80.0255),
    "galle": Location("galle", "Galle", 6.0535, 80.2210),
    "anuradhapura": Location("anuradhapura", "Anuradhapura", 8.3114, 80.4037),
}


@dataclass(frozen=True)
class WeatherSource:
    """One downloadable weather series.

    `forecast_lead_hours` is 24 only for the previous-day-1 series, where the
    API itself defines the lead. Live forecasts fill the column later from
    the clock, so it stays None here.
    """

    cli_name: str
    source_id: str
    data_kind: str
    description: str
    kind: str
    endpoint: str
    forecast_lead_hours: float | None
    variable_suffix: str
    default_model: str | None
    default_chunk_days: int
    default_end_lag_days: int
    timeout_s: int
    attribution: str
    licence_name: str
    licence_url: str


WEATHER_SOURCES: dict[str, WeatherSource] = {
    "open-meteo-archive": WeatherSource(
        cli_name="open-meteo-archive",
        source_id="open_meteo_archive",
        data_kind="reanalysis",
        description=(
            "Open-Meteo Historical Weather API. With models=era5 this is ERA5 "
            "reanalysis, not a forecast."
        ),
        kind="open_meteo",
        endpoint="https://archive-api.open-meteo.com/v1/archive",
        forecast_lead_hours=None,
        variable_suffix="",
        default_model="era5",
        default_chunk_days=366,
        default_end_lag_days=7,
        timeout_s=120,
        attribution=OPEN_METEO_ATTRIBUTION,
        licence_name=OPEN_METEO_LICENCE_NAME,
        licence_url=OPEN_METEO_LICENCE_URL,
    ),
    "open-meteo-historical-forecast": WeatherSource(
        cli_name="open-meteo-historical-forecast",
        source_id="open_meteo_historical_forecast",
        data_kind="model_initial_hours",
        description=(
            "Open-Meteo Historical Forecast API. A continuous series made by "
            "stitching the first hours of each forecast run. It tracks recent "
            "conditions. It is not the forecast that was issued a day ahead, "
            "and it is kept apart from the reanalysis files."
        ),
        kind="open_meteo",
        endpoint="https://historical-forecast-api.open-meteo.com/v1/forecast",
        forecast_lead_hours=None,
        variable_suffix="",
        default_model=None,
        default_chunk_days=31,
        default_end_lag_days=2,
        timeout_s=180,
        attribution=OPEN_METEO_ATTRIBUTION,
        licence_name=OPEN_METEO_LICENCE_NAME,
        licence_url=OPEN_METEO_LICENCE_URL,
    ),
    "open-meteo-previous-day1": WeatherSource(
        cli_name="open-meteo-previous-day1",
        source_id="open_meteo_previous_day1",
        data_kind="forecast",
        description=(
            "Open-Meteo Previous Runs API, lead of about 24 hours "
            "(_previous_day1). This is the series to train on when the live "
            "model will be fed a forecast rather than an observation. Kept "
            "apart from reanalysis."
        ),
        kind="open_meteo",
        endpoint="https://previous-runs-api.open-meteo.com/v1/forecast",
        forecast_lead_hours=24.0,
        variable_suffix="_previous_day1",
        default_model=None,
        default_chunk_days=31,
        default_end_lag_days=2,
        timeout_s=180,
        attribution=OPEN_METEO_ATTRIBUTION,
        licence_name=OPEN_METEO_LICENCE_NAME,
        licence_url=OPEN_METEO_LICENCE_URL,
    ),
    "nasa-power": WeatherSource(
        cli_name="nasa-power",
        source_id="nasa_power",
        data_kind="satellite_model",
        description=(
            "NASA POWER hourly point data. Satellite-based radiation plus "
            "assimilated meteorology. A second radiation source, not a forecast."
        ),
        kind="nasa",
        endpoint=NASA_POWER_URL,
        forecast_lead_hours=None,
        variable_suffix="",
        default_model=None,
        default_chunk_days=120,
        default_end_lag_days=7,
        timeout_s=180,
        attribution=NASA_POWER_ATTRIBUTION,
        licence_name="US government work; acknowledgement requested",
        licence_url=NASA_POWER_HOME,
    ),
}


WEATHER_COLUMNS = [
    "timestamp",
    "location_id",
    "latitude",
    "longitude",
    "grid_latitude",
    "grid_longitude",
    "grid_elevation_m",
    "source",
    "data_kind",
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
    "retrieved_at_utc",
]

# direct_horizontal_wm2 is Open-Meteo's direct_radiation (beam on a horizontal
# plane). NASA POWER is not asked for a separate horizontal-beam series, so
# that column is empty in NASA files. DNI is direct_normal_irradiance.

PV_COLUMNS = [
    "timestamp",
    "location_id",
    "latitude",
    "longitude",
    "weather_source",
    "weather_data_kind",
    "system_kw",
    "tilt_deg",
    "azimuth_deg",
    "inverter_ac_limit_kw",
    "temp_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "cloud_cover_pct",
    "wind_speed_ms",
    "ghi_wm2",
    "dni_wm2",
    "dhi_wm2",
    "poa_global_wm2_simulated",
    "cell_temp_c_simulated",
    "pv_dc_kw_simulated",
    "pv_ac_kw_simulated",
    "is_simulated",
]

OPEN_METEO_HOURLY = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "direct_normal_irradiance",
]

# Map an Open-Meteo variable (without any _previous_day suffix) to our column.
OPEN_METEO_COLUMN = {
    "temperature_2m": "temp_c",
    "relative_humidity_2m": "relative_humidity_pct",
    "precipitation": "precipitation_mm",
    "cloud_cover": "cloud_cover_pct",
    "wind_speed_10m": "wind_speed_ms",
    "shortwave_radiation": "ghi_wm2",
    "direct_normal_irradiance": "dni_wm2",
    "diffuse_radiation": "dhi_wm2",
    "direct_radiation": "direct_horizontal_wm2",
}

NASA_PARAMETERS = [
    "T2M",
    "RH2M",
    "PRECTOTCORR",
    "CLOUD_AMT",
    "WS10M",
    "ALLSKY_SFC_SW_DWN",
    "ALLSKY_SFC_SW_DNI",
    "ALLSKY_SFC_SW_DIFF",
]

NASA_COLUMN = {
    "T2M": "temp_c",
    "RH2M": "relative_humidity_pct",
    "PRECTOTCORR": "precipitation_mm",
    "CLOUD_AMT": "cloud_cover_pct",
    "WS10M": "wind_speed_ms",
    "ALLSKY_SFC_SW_DWN": "ghi_wm2",
    "ALLSKY_SFC_SW_DNI": "dni_wm2",
    "ALLSKY_SFC_SW_DIFF": "dhi_wm2",
}

LIVE_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
LIVE_CURRENT = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
]
