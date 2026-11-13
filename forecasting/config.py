"""Constants for the daily PV forecast.

Issue time is local midnight in Asia/Colombo. Each issue covers the following
24 hours and nothing after that. The pilot reads the resulting file. It does
not command an inverter.
"""

from __future__ import annotations

from pathlib import Path

from data.pipeline.config import TIMEZONE

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO_ROOT / "forecasting" / "models"
FORECAST_DIR = REPO_ROOT / "data" / "processed" / "forecasts"
WORK_DIR = REPO_ROOT / "data" / "raw" / "simulated_forecast"
WEATHER_CACHE_DIR = REPO_ROOT / "data" / "raw" / "forecast_cache"
EXAMPLE_SITES = REPO_ROOT / "forecasting" / "sites.example.csv"

RESOLUTION_FREQ = {
    "hourly": "1h",
    "15min": "15min",
}

# Chosen before any test score. Not fitted to the series.
# 0.85 stands in for inverter efficiency, soiling and a typical temperature loss.
BASELINE_LOSS_FACTOR = 0.85
BASELINE_ALBEDO = 0.20

# The synthetic inverter is deliberately not the same formula as the baseline.
SYNTHETIC_LOSS_FACTOR = 0.80
SYNTHETIC_TEMP_COEFF = -0.004
SYNTHETIC_TEMP_REF_C = 25.0

CLOUDY_DAY_CLOUD_PCT = 60.0
MIDDAY_HOURS = (11, 12, 13)
HORIZON = "24h"
TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15

# One model for every home. The target during training is pv_kw / system_kw.
# tilt and azimuth are site metadata, known before the issue time.
FEATURE_COLUMNS = [
    "hour",
    "day_of_year",
    "solar_zenith_deg",
    "solar_azimuth_deg",
    "solar_elevation_deg",
    "ghi_wm2",
    "dni_wm2",
    "dhi_wm2",
    "cloud_cover_pct",
    "temp_c",
    "lag_24h_norm",
    "lag_48h_norm",
    "recent_norm",
    "system_kw",
    "tilt_deg",
    "azimuth_deg",
]

WEATHER_COLUMNS = [
    "ghi_wm2",
    "dni_wm2",
    "dhi_wm2",
    "cloud_cover_pct",
    "temp_c",
]

SITE_COLUMNS = [
    "site_id",
    "system_kw",
    "tilt_deg",
    "azimuth_deg",
    "latitude",
    "longitude",
]

READING_COLUMNS = ["site_id", "timestamp", "pv_kw"]

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_VARIABLES = [
    "temperature_2m",
    "cloud_cover",
    "shortwave_radiation",
    "direct_normal_irradiance",
    "diffuse_radiation",
]
OPEN_METEO_TO_COLUMN = {
    "temperature_2m": "temp_c",
    "cloud_cover": "cloud_cover_pct",
    "shortwave_radiation": "ghi_wm2",
    "direct_normal_irradiance": "dni_wm2",
    "diffuse_radiation": "dhi_wm2",
}

DEFAULT_LGBM_PARAMS = {
    "objective": "regression",
    "metric": "l1",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.9,
    "bagging_freq": 1,
    "verbosity": -1,
    "seed": 7,
    "num_threads": 1,
    "force_row_wise": True,
    "deterministic": True,
}
DEFAULT_N_ESTIMATORS = 400
DEFAULT_EARLY_STOPPING = 40

# Fixed dates so a synthetic run can be repeated.
DEFAULT_SYNTHETIC_START = "2024-06-01"
DEFAULT_SYNTHETIC_END = "2024-08-29"
