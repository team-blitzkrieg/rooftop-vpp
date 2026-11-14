"""Household demand forecast tests. No network calls. Figures are SIMULATED."""

from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from forecasting.baseline import similar_day_baseline
from forecasting.calendar import is_holiday
from forecasting.cli import main
from forecasting.config import DEMAND_FEATURE_COLUMNS, TIMEZONE
from forecasting.features import assert_no_target_leakage, build_frame
from forecasting.synthetic import generate_simulated
from forecasting.tables import load_sites, with_consumption


def test_holiday_flag_matches_the_2024_gazette_dates_in_the_window():
    assert is_holiday(datetime(2024, 6, 17).date())
    assert is_holiday(datetime(2024, 6, 21).date())
    assert is_holiday(datetime(2024, 8, 19).date())
    assert not is_holiday(datetime(2025, 6, 17).date())
    assert not is_holiday(datetime(2024, 6, 18).date())


def test_demand_features_do_not_see_the_issue_day():
    sites = load_sites("forecasting/sites.example.csv")
    readings, weather = generate_simulated(
        sites,
        datetime(2024, 6, 1).date(),
        datetime(2024, 6, 21).date(),
        "hourly",
        seed=7,
    )
    frame = build_frame(readings, sites, weather, target="demand")
    assert list(DEMAND_FEATURE_COLUMNS) == [
        "hour",
        "day_of_year",
        "day_of_week",
        "is_weekend",
        "is_holiday",
        "temp_c",
        "lag_24h_kw",
        "lag_168h_kw",
        "recent_kw",
        "demand_scale_kw",
    ]
    assert "consumption_kw" not in DEMAND_FEATURE_COLUMNS
    assert_no_target_leakage(
        frame,
        feature_columns=DEMAND_FEATURE_COLUMNS,
        lag_time_columns=("lag_24h_at", "lag_168h_at", "recent_at"),
    )
    known = frame["lag_24h_at"].notna()
    assert (frame.loc[known, "lag_24h_at"] < frame.loc[known, "issued_at"]).all()
    # 17 June 2024 is Id-Ul-Allah, a Monday, so the holiday flag is not just the weekend bit.
    holiday_rows = frame.loc[frame["timestamp"].dt.date == datetime(2024, 6, 17).date()]
    assert not holiday_rows.empty
    assert (holiday_rows["is_holiday"] == 1.0).all()
    assert (holiday_rows["is_weekend"] == 0.0).all()


def test_similar_day_baseline_is_non_negative_and_ignores_the_issue_day():
    timestamps = pd.date_range("2024-06-03", periods=24 * 8, freq="1h", tz=TIMEZONE)
    # Constant 1.5 kW on the hour, except the last day which is 9 kW and must not leak backward.
    consumption = np.full(len(timestamps), 1.5)
    consumption[timestamps.day >= 10] = 9.0
    frame = pd.DataFrame(
        {
            "site_id": "home-test",
            "timestamp": timestamps,
            "issued_at": timestamps.tz_convert(TIMEZONE).normalize(),
            "consumption_kw": consumption,
        }
    )
    baseline = similar_day_baseline(frame, lookback_days=28)
    assert (baseline.dropna() >= 0).all()
    last_day = timestamps.day == timestamps.day.max()
    # Last Monday-like hours that match earlier weekdays should still see 1.5, not 9.
    earlier = baseline.loc[~last_day].dropna()
    assert earlier.max() <= 1.5 + 1e-9
    assert not (baseline < 0).any()


def test_home_without_a_meter_is_skipped_with_a_message():
    sites = pd.DataFrame(
        [
            {"site_id": "home-metered", "has_meter": True},
            {"site_id": "home-none", "has_meter": False},
        ]
    )
    timestamps = pd.date_range("2024-06-01", periods=3, freq="1h", tz=TIMEZONE)
    readings = pd.DataFrame(
        {
            "site_id": ["home-metered"] * 3 + ["home-none"] * 3,
            "timestamp": list(timestamps) * 2,
            "consumption_kw": [0.4, 0.5, 0.6, 1.0, 1.0, 1.0],
        }
    )
    kept, messages = with_consumption(readings, sites)
    assert set(kept["site_id"]) == {"home-metered"}
    assert any("Skipping home-none: no consumption meter." == message for message in messages)


def test_negative_consumption_file_is_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "site_id,timestamp,consumption_kw\nhome-a,2024-06-01T00:00:00+05:30,-0.2\n",
        encoding="utf-8",
    )
    from forecasting.tables import load_readings

    with pytest.raises(ValueError, match="negative consumption_kw"):
        load_readings(path)


def test_demand_train_smoke_writes_net_load(tmp_path, capsys):
    code = main(
        [
            "train",
            "--target",
            "demand",
            "--synthetic",
            "--start",
            "2024-06-01",
            "--end",
            "2024-07-07",
            "--estimators",
            "40",
            "--model-dir",
            str(tmp_path / "models"),
            "--forecast-dir",
            str(tmp_path / "forecasts"),
            "--work-dir",
            str(tmp_path / "work"),
        ]
    )
    assert code == 0
    printed = capsys.readouterr().out
    assert "SIMULATED" in printed
    assert "does not control any equipment" in printed
    assert "baseline" in printed
    assert "lightgbm" in printed
    versions = list((tmp_path / "models").iterdir())
    assert len(versions) == 1
    record = json.loads((versions[0] / "experiment.json").read_text(encoding="utf-8"))
    assert record["forecast_target"] == "demand"
    assert record["controls_equipment"] is False
    assert record["data_label"] == "SIMULATED"
    assert set(record["metrics"]["test"]) == {"overall", "evening", "weekend"}
    files = list((tmp_path / "forecasts").rglob("*.csv"))
    assert files
    sample = pd.read_csv(files[0], comment="#")
    assert {"consumption_kw", "baseline_kw", "pv_baseline_kw", "net_kw"}.issubset(sample.columns)
    assert (sample["consumption_kw"] >= -1e-9).all()
    assert (sample["baseline_kw"].dropna() >= -1e-9).all()
