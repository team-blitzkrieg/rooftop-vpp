"""Forecast tests. No network calls."""

from __future__ import annotations

import json
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from data.pipeline.http_client import HttpClient
from forecasting.baseline import baseline_kw
from forecasting.cli import main
from forecasting.config import FEATURE_COLUMNS, TIMEZONE
from forecasting.features import assert_no_target_leakage, build_frame
from forecasting.split import IssueSplit, LeakageError, assert_chronological, split_by_issue
from forecasting.synthetic import default_sites, generate_simulated
from forecasting.weather import fetch_weather

COLOMBO_LAT = 6.9271
COLOMBO_LON = 79.8612


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.headers = {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _site_row():
    return pd.DataFrame(
        [
            {
                "site_id": "home-test",
                "name": "Test",
                "location_id": "colombo",
                "system_kw": 5.0,
                "tilt_deg": 10.0,
                "azimuth_deg": 180.0,
                "latitude": COLOMBO_LAT,
                "longitude": COLOMBO_LON,
                "timezone": TIMEZONE,
            }
        ]
    )


def _three_days():
    timestamps = pd.date_range("2024-06-01", periods=72, freq="1h", tz=TIMEZONE)
    day_number = timestamps.day - timestamps.day.min() + 1
    readings = pd.DataFrame(
        {
            "site_id": "home-test",
            "timestamp": timestamps,
            "pv_kw": day_number.astype(float),
            "is_simulated": True,
            "data_label": "SIMULATED",
        }
    )
    weather = pd.DataFrame(
        {
            "site_id": "home-test",
            "timestamp": timestamps,
            "ghi_wm2": 0.0,
            "dni_wm2": 0.0,
            "dhi_wm2": 0.0,
            "cloud_cover_pct": 10.0,
            "temp_c": 28.0,
            "is_simulated": True,
            "data_label": "SIMULATED",
        }
    )
    weather["ghi_wm2"] = np.where(timestamps.hour.isin([10, 11, 12, 13, 14]), 700.0, 0.0)
    weather["dni_wm2"] = weather["ghi_wm2"] * 0.7
    weather["dhi_wm2"] = weather["ghi_wm2"] * 0.3
    return readings, weather


def test_split_keeps_issue_days_in_time_order():
    issued = pd.date_range("2024-06-01", periods=10, freq="D", tz=TIMEZONE)
    frame = pd.DataFrame(
        {
            "issued_at": list(issued) * 2,
            "site_id": ["a"] * 10 + ["b"] * 10,
            "pv_kw": 1.0,
        }
    )
    split = split_by_issue(frame, train_fraction=0.7, val_fraction=0.2)
    assert split.train["issued_at"].max() < split.val["issued_at"].min()
    assert split.val["issued_at"].max() < split.test["issued_at"].min()
    assert split.train["issued_at"].nunique() == 7
    assert split.val["issued_at"].nunique() == 2
    assert split.test["issued_at"].nunique() == 1
    assert_chronological(split)


def test_split_rejects_a_shuffled_assignment():
    issued = pd.date_range("2024-06-01", periods=6, freq="D", tz=TIMEZONE)
    frame = pd.DataFrame({"issued_at": issued, "site_id": "a", "pv_kw": 1.0})
    split = split_by_issue(frame, 0.5, 0.16)
    swapped = IssueSplit(train=split.test, val=split.val, test=split.train)
    with pytest.raises(LeakageError):
        assert_chronological(swapped)


def test_features_use_yesterday_and_ignore_the_issue_day():
    readings, weather = _three_days()
    sites = _site_row()
    frame = build_frame(readings, sites, weather)
    assert list(FEATURE_COLUMNS) == [column for column in FEATURE_COLUMNS if column in frame.columns]
    assert "pv_kw" not in FEATURE_COLUMNS

    noon = pd.Timestamp("2024-06-02 12:00", tz=TIMEZONE)
    row = frame.loc[frame["timestamp"] == noon].iloc[0]
    assert row["lag_24h_norm"] == pytest.approx(1.0 / 5.0)
    assert pd.isna(row["lag_48h_norm"])
    assert row["recent_norm"] == pytest.approx(1.0 / 5.0)
    assert row["lag_24h_at"] < row["issued_at"]
    assert row["solar_elevation_deg"] > 0

    night = frame.loc[frame["timestamp"] == pd.Timestamp("2024-06-02 02:00", tz=TIMEZONE)].iloc[0]
    assert night["solar_elevation_deg"] < 0

    third = frame.loc[frame["timestamp"] == pd.Timestamp("2024-06-03 15:00", tz=TIMEZONE)].iloc[0]
    assert third["lag_24h_norm"] == pytest.approx(2.0 / 5.0)
    assert third["lag_48h_norm"] == pytest.approx(1.0 / 5.0)
    assert third["recent_norm"] == pytest.approx(2.0 / 5.0)

    corrupted = readings.copy()
    last_day = corrupted["timestamp"] >= pd.Timestamp("2024-06-03", tz=TIMEZONE)
    corrupted.loc[last_day, "pv_kw"] = 9.0
    again = build_frame(corrupted, sites, weather)
    left = frame.loc[frame["issued_at"] == frame["issued_at"].max(), FEATURE_COLUMNS].reset_index(drop=True)
    right = again.loc[again["issued_at"] == again["issued_at"].max(), FEATURE_COLUMNS].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)

    leaked = frame.copy()
    leaked.loc[leaked["timestamp"] == noon, "lag_24h_at"] = leaked.loc[leaked["timestamp"] == noon, "issued_at"]
    with pytest.raises(LeakageError):
        assert_no_target_leakage(leaked)


def test_baseline_is_zero_at_night_and_never_above_nameplate():
    night = pd.Timestamp("2024-06-15 02:00", tz=TIMEZONE)
    noon = pd.Timestamp("2024-06-15 12:00", tz=TIMEZONE)
    dark = baseline_kw(
        [night],
        latitude=COLOMBO_LAT,
        longitude=COLOMBO_LON,
        tilt_deg=10,
        azimuth_deg=180,
        system_kw=5,
        ghi_wm2=[900],
        dni_wm2=[900],
        dhi_wm2=[200],
    )
    assert dark[0] == 0.0

    capped = baseline_kw(
        [noon],
        latitude=COLOMBO_LAT,
        longitude=COLOMBO_LON,
        tilt_deg=10,
        azimuth_deg=180,
        system_kw=5,
        ghi_wm2=[5000],
        dni_wm2=[5000],
        dhi_wm2=[500],
    )
    assert 0.0 < capped[0] <= 5.0

    small = baseline_kw(
        [noon],
        latitude=COLOMBO_LAT,
        longitude=COLOMBO_LON,
        tilt_deg=10,
        azimuth_deg=180,
        system_kw=3,
        ghi_wm2=[500],
        dni_wm2=[400],
        dhi_wm2=[100],
    )
    large = baseline_kw(
        [noon],
        latitude=COLOMBO_LAT,
        longitude=COLOMBO_LON,
        tilt_deg=10,
        azimuth_deg=180,
        system_kw=6,
        ghi_wm2=[500],
        dni_wm2=[400],
        dhi_wm2=[100],
    )
    assert small[0] > 0
    assert large[0] == pytest.approx(small[0] * 2)
    assert large[0] <= 6


def test_synthetic_series_is_labelled_and_dark_at_night():
    sites = default_sites().head(1)
    readings, weather = generate_simulated(
        sites,
        date(2024, 6, 1),
        date(2024, 6, 2),
        "hourly",
        seed=1,
    )
    assert (readings["data_label"] == "SIMULATED").all()
    assert readings["is_simulated"].all()
    assert (weather["data_label"] == "SIMULATED").all()
    assert weather["weather_kind"].eq("forecast").all()
    night = readings["timestamp"].dt.hour <= 4
    assert (readings.loc[night, "pv_kw"] == 0).all()
    assert readings["pv_kw"].max() <= float(sites.iloc[0]["system_kw"])

    quarter, _ = generate_simulated(
        sites,
        date(2024, 6, 1),
        date(2024, 6, 1),
        "15min",
        seed=1,
    )
    assert len(quarter) == 96
    assert (quarter["data_label"] == "SIMULATED").all()


def test_weather_cache_skips_the_second_request(tmp_path):
    hours = ["2024-06-01T00:00", "2024-06-01T01:00"]
    payload = {
        "hourly": {
            "time": hours,
            "temperature_2m": [27.0, 26.5],
            "cloud_cover": [12, 40],
            "shortwave_radiation": [0.0, 0.0],
            "direct_normal_irradiance": [0.0, 0.0],
            "diffuse_radiation": [0.0, 0.0],
        }
    }
    session = FakeSession([FakeResponse(200, payload)])
    client = HttpClient(session=session, pause_s=0, max_retries=0, timeout_s=5)
    sites = default_sites().head(1)
    first = fetch_weather(
        sites,
        date(2024, 6, 1),
        date(2024, 6, 1),
        kind="forecast",
        resolution="hourly",
        cache_dir=tmp_path,
        client=client,
    )
    second = fetch_weather(
        sites,
        date(2024, 6, 1),
        date(2024, 6, 1),
        kind="forecast",
        resolution="hourly",
        cache_dir=tmp_path,
        client=client,
    )
    assert len(session.calls) == 1
    assert str(first["timestamp"].dt.tz) == TIMEZONE
    assert list(second["ghi_wm2"]) == [0.0, 0.0]
    assert (first["data_label"] == "MEASURED").all()
    with pytest.raises(ValueError, match="hourly"):
        fetch_weather(
            sites,
            date(2024, 6, 1),
            date(2024, 6, 1),
            kind="historical",
            resolution="15min",
            cache_dir=tmp_path,
            client=client,
        )


def test_train_on_synthetic_data_writes_a_forecast(tmp_path, capsys):
    code = main(
        [
            "train",
            "--synthetic",
            "--start",
            "2024-06-01",
            "--end",
            "2024-06-14",
            "--resolution",
            "hourly",
            "--seed",
            "7",
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
    text = capsys.readouterr().out
    assert "SIMULATED" in text
    assert "does not control any equipment" in text
    assert "baseline" in text
    assert "lightgbm" in text

    experiment_path = next((tmp_path / "models").glob("*/experiment.json"))
    record = json.loads(experiment_path.read_text(encoding="utf-8"))
    assert record["data_label"] == "SIMULATED"
    assert record["controls_equipment"] is False
    assert record["metrics"]["test"]["overall"]["baseline"]["mae_kw"] >= 0
    assert record["metrics"]["test"]["overall"]["lightgbm"]["n"] > 0
    assert "pv_kw" not in record["features"]
    markdown = experiment_path.with_suffix(".md").read_text(encoding="utf-8")
    assert "SIMULATED" in markdown

    forecasts = list((tmp_path / "forecasts").glob("*/*/*.csv"))
    assert forecasts
    sample = pd.read_csv(forecasts[0])
    assert (sample["data_label"] == "SIMULATED").all()
    assert sample["pv_kw"].max() <= sample["system_kw"].max() + 1e-6
    assert (sample["pv_kw"] >= 0).all()
    stamps = pd.to_datetime(sample["timestamp"])
    night = stamps.dt.hour <= 4
    assert (sample.loc[night, "pv_kw"] == 0).all()
    assert (sample.loc[night, "baseline_kw"] == 0).all()

    readings = (tmp_path / "work" / "readings.csv").read_text(encoding="utf-8")
    assert "SIMULATED" in readings

    code = main(
        [
            "forecast",
            "--model",
            str(experiment_path.parent),
            "--site",
            "home-dehiwala",
            "--date",
            "2024-06-14",
            "--sites",
            str(tmp_path / "work" / "sites.csv"),
            "--readings",
            str(tmp_path / "work" / "readings.csv"),
            "--weather",
            str(tmp_path / "work" / "weather.csv"),
            "--forecast-dir",
            str(tmp_path / "one-day"),
        ]
    )
    assert code == 0
    one_day = tmp_path / "one-day"
    written = list(one_day.glob("*/*/*.csv"))
    assert len(written) == 1
    assert "home-dehiwala" in str(written[0])
    again = pd.read_csv(written[0])
    assert len(again) == 24
    assert (again["data_label"] == "SIMULATED").all()
    assert (again["pv_kw"] >= 0).all()
