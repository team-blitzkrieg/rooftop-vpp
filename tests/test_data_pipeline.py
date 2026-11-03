"""Pipeline tests. These use made-up payloads and do not call the network."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest
import requests

from data.pipeline.config import LOCATIONS, WEATHER_COLUMNS, WEATHER_SOURCES
from data.pipeline.http_client import HttpClient
from data.pipeline.nasa_power import nasa_payload_to_frame
from data.pipeline.open_meteo import (
    fetch_open_meteo,
    hourly_payload_to_frame,
    parse_live_payload,
)
from data.pipeline.pvsim import simulate_pv
from data.pipeline.samples import export_live_snapshot, export_month
from data.pipeline.tables import (
    clip_to_local_days,
    date_chunks,
    read_weather_csv,
    slice_month,
    write_dataset,
)

COLOMBO = LOCATIONS["colombo"]
UNITS = {
    "time": "iso8601",
    "temperature_2m": "°C",
    "relative_humidity_2m": "%",
    "precipitation": "mm",
    "cloud_cover": "%",
    "wind_speed_10m": "m/s",
    "shortwave_radiation": "W/m²",
    "direct_radiation": "W/m²",
    "diffuse_radiation": "W/m²",
    "direct_normal_irradiance": "W/m²",
}


def _hours(day: str, n: int = 24) -> list[str]:
    start = datetime.fromisoformat(day + "T00:00")
    return [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(n)]


def _series(n: int, value: float) -> list[float]:
    return [value] * n


def open_meteo_payload(day: str, *, suffix: str = "", n: int = 24) -> dict:
    times = _hours(day, n)
    hourly = {"time": times}
    units = {"time": "iso8601"}
    for name, unit in UNITS.items():
        if name == "time":
            continue
        hourly[name + suffix] = _series(len(times), 1.0 if "radiation" in name or name.startswith("shortwave") or name.startswith("direct") or name.startswith("diffuse") else 25.0)
        units[name + suffix] = unit
    hourly["temperature_2m" + suffix] = _series(len(times), 28.0)
    hourly["wind_speed_10m" + suffix] = _series(len(times), 2.5)
    hourly["shortwave_radiation" + suffix] = _series(len(times), 0.0)
    hourly["direct_radiation" + suffix] = _series(len(times), 0.0)
    hourly["diffuse_radiation" + suffix] = _series(len(times), 0.0)
    hourly["direct_normal_irradiance" + suffix] = _series(len(times), 0.0)
    return {
        "latitude": 6.9,
        "longitude": 79.9,
        "elevation": 9.0,
        "hourly_units": units,
        "hourly": hourly,
    }


class FakeResponse:
    def __init__(self, status, payload=None, headers=None, text=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}
        self.text = text if text is not None else (json.dumps(payload) if payload is not None else "")

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
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


def test_locations_cover_the_five_cities():
    assert list(LOCATIONS) == ["colombo", "kandy", "jaffna", "galle", "anuradhapura"]
    assert LOCATIONS["colombo"].latitude == pytest.approx(6.9271)
    assert LOCATIONS["colombo"].longitude == pytest.approx(79.8612)


def test_date_chunks_cover_the_range_without_overlap():
    chunks = date_chunks(date(2024, 1, 1), date(2024, 1, 10), 4)
    assert chunks == [
        (date(2024, 1, 1), date(2024, 1, 4)),
        (date(2024, 1, 5), date(2024, 1, 8)),
        (date(2024, 1, 9), date(2024, 1, 10)),
    ]
    with pytest.raises(ValueError):
        date_chunks(date(2024, 1, 2), date(2024, 1, 1), 7)


def test_open_meteo_archive_frame_is_colombo_time_and_not_a_forecast():
    source = WEATHER_SOURCES["open-meteo-archive"]
    frame = hourly_payload_to_frame(
        open_meteo_payload("2024-06-01"),
        location=COLOMBO,
        source=source,
        retrieved_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
        variable_suffix="",
    )
    assert str(frame["timestamp"].dt.tz) == "Asia/Colombo"
    assert frame["timestamp"].iloc[0].isoformat() == "2024-06-01T00:00:00+05:30"
    assert frame["source"].iloc[0] == "open_meteo_archive"
    assert frame["data_kind"].iloc[0] == "reanalysis"
    assert frame["forecast_lead_hours"].isna().all()
    assert frame["ghi_wm2"].iloc[0] == 0.0
    assert frame["temp_c"].iloc[0] == 28.0
    assert frame["grid_elevation_m"].iloc[0] == 9.0
    assert set(WEATHER_COLUMNS).issuperset(frame.columns)


def test_previous_day_suffix_is_a_24_hour_forecast():
    source = WEATHER_SOURCES["open-meteo-previous-day1"]
    payload = open_meteo_payload("2024-06-01", suffix="_previous_day1")
    frame = hourly_payload_to_frame(
        payload,
        location=COLOMBO,
        source=source,
        retrieved_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
        variable_suffix="_previous_day1",
    )
    assert frame["source"].iloc[0] == "open_meteo_previous_day1"
    assert frame["data_kind"].iloc[0] == "forecast"
    assert set(frame["forecast_lead_hours"]) == {24.0}
    assert frame["temp_c"].iloc[0] == 28.0
    assert "temperature_2m_previous_day1" not in frame.columns


def test_bad_wind_unit_is_rejected():
    payload = open_meteo_payload("2024-06-01")
    payload["hourly_units"]["wind_speed_10m"] = "km/h"
    source = WEATHER_SOURCES["open-meteo-archive"]
    with pytest.raises(ValueError, match="m/s"):
        hourly_payload_to_frame(
            payload,
            location=COLOMBO,
            source=source,
            retrieved_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
            variable_suffix="",
        )


def test_fetch_open_meteo_stitches_chunks():
    source = WEATHER_SOURCES["open-meteo-archive"]

    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_json(self, url, params):
            self.calls.append(params)
            return open_meteo_payload(params["start_date"])

    client = FakeClient()
    frame = fetch_open_meteo(
        source,
        COLOMBO,
        date(2024, 6, 1),
        date(2024, 6, 2),
        client,
        model="era5",
        chunk_days=1,
        retrieved_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )
    assert len(client.calls) == 2
    assert client.calls[0]["models"] == "era5"
    assert client.calls[0]["timezone"] == "Asia/Colombo"
    assert client.calls[0]["wind_speed_unit"] == "ms"
    assert len(frame) == 48
    assert frame["timestamp"].is_monotonic_increasing


def test_nasa_fill_value_and_half_hour_colombo_time():
    parameters = {}
    for name in ("T2M", "RH2M", "PRECTOTCORR", "CLOUD_AMT", "WS10M", "ALLSKY_SFC_SW_DWN", "ALLSKY_SFC_SW_DNI", "ALLSKY_SFC_SW_DIFF"):
        parameters[name] = {"2024010100": 10.0, "2024010101": -999.0}
    parameters["ALLSKY_SFC_SW_DWN"]["2024010100"] = 0.0
    payload = {
        "header": {"fill_value": -999.0, "time_standard": "UTC"},
        "geometry": {"coordinates": [79.861, 6.927, 12.0]},
        "properties": {"parameter": parameters},
    }
    frame = nasa_payload_to_frame(
        payload,
        location=COLOMBO,
        retrieved_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )
    assert str(frame["timestamp"].dt.tz) == "Asia/Colombo"
    assert frame["timestamp"].iloc[0].isoformat() == "2024-01-01T05:30:00+05:30"
    assert frame["ghi_wm2"].iloc[0] == 0.0
    assert pd.isna(frame["ghi_wm2"].iloc[1])
    assert pd.isna(frame["temp_c"].iloc[1])
    assert frame["source"].iloc[0] == "nasa_power"
    assert frame["data_kind"].iloc[0] == "satellite_model"
    assert frame["forecast_lead_hours"].isna().all()
    assert pd.isna(frame["direct_horizontal_wm2"].iloc[0])
    assert frame["grid_elevation_m"].iloc[0] == 12.0


def test_live_payload_splits_current_hourly_and_15_min():
    hourly = open_meteo_payload("2026-11-03", n=2)
    minutely = open_meteo_payload("2026-11-03", n=2)
    minutely["minutely_15"] = minutely.pop("hourly")
    minutely["minutely_15_units"] = minutely.pop("hourly_units")
    payload = hourly
    payload["minutely_15"] = minutely["minutely_15"]
    payload["minutely_15_units"] = minutely["minutely_15_units"]
    # Two 15-minute stamps, not two hours, so the lead times differ from hourly.
    payload["minutely_15"]["time"] = ["2026-11-03T00:00", "2026-11-03T00:15"]
    payload["current"] = {
        "time": "2026-11-03T00:00",
        "temperature_2m": 27.0,
        "relative_humidity_2m": 80,
        "precipitation": 0.0,
        "cloud_cover": 40,
        "wind_speed_10m": 1.2,
    }
    retrieved = datetime(2026, 11, 2, 18, 30, tzinfo=timezone.utc)  # 2026-11-03 00:00 in Colombo
    frames = parse_live_payload(payload, location=COLOMBO, retrieved_at=retrieved)
    assert len(frames["hourly"]) == 2
    assert len(frames["minutely_15"]) == 2
    assert len(frames["current"]) == 1
    assert frames["hourly"]["data_kind"].iloc[0] == "forecast"
    assert frames["current"]["data_kind"].iloc[0] == "current"
    assert frames["hourly"]["forecast_lead_hours"].iloc[0] == pytest.approx(0.0)
    assert frames["hourly"]["forecast_lead_hours"].iloc[1] == pytest.approx(1.0)
    assert frames["minutely_15"]["forecast_lead_hours"].iloc[1] == pytest.approx(0.25)
    assert frames["current"]["temp_c"].iloc[0] == 27.0
    assert pd.isna(frames["current"]["ghi_wm2"].iloc[0])


def test_http_retries_a_429_then_reads_json():
    session = FakeSession(
        [
            FakeResponse(429, {"error": True, "reason": "busy"}, headers={"Retry-After": "0"}),
            FakeResponse(200, {"ok": True}),
        ]
    )
    client = HttpClient(session, pause_s=0, max_retries=2, sleep=lambda _seconds: None)
    assert client.get_json("https://example.test/v1", {"q": 1}) == {"ok": True}
    assert len(session.calls) == 2


def test_http_does_not_retry_a_400():
    session = FakeSession([FakeResponse(400, text="bad date")])
    client = HttpClient(session, pause_s=0, max_retries=4, sleep=lambda _seconds: None)
    with pytest.raises(requests.HTTPError, match="400"):
        client.get_json("https://example.test/v1", {})
    assert len(session.calls) == 1


def test_http_retries_a_dropped_connection():
    session = FakeSession(
        [
            requests.ConnectionError("reset"),
            FakeResponse(200, {"hourly": {}}),
        ]
    )
    client = HttpClient(session, pause_s=0, max_retries=2, sleep=lambda _seconds: None)
    assert client.get_json("https://example.test/v1", {}) == {"hourly": {}}
    assert len(session.calls) == 2


def _weather_row(when: str, *, ghi, dni, dhi, temp, wind=1.0) -> dict:
    return {
        "timestamp": pd.Timestamp(when, tz="Asia/Colombo"),
        "location_id": "colombo",
        "latitude": COLOMBO.latitude,
        "longitude": COLOMBO.longitude,
        "grid_elevation_m": 9.0,
        "source": "open_meteo_archive",
        "data_kind": "reanalysis",
        "temp_c": temp,
        "relative_humidity_pct": 70,
        "precipitation_mm": 0.0,
        "cloud_cover_pct": 20,
        "wind_speed_ms": wind,
        "ghi_wm2": ghi,
        "dni_wm2": dni,
        "dhi_wm2": dhi,
    }


def test_simulated_pv_is_labelled_zero_at_night_and_clipped():
    night = _weather_row("2024-06-15 00:00", ghi=0, dni=0, dhi=0, temp=25)
    day = _weather_row("2024-06-15 12:00", ghi=500, dni=300, dhi=200, temp=25)
    bright = _weather_row("2024-06-15 12:00", ghi=3000, dni=2500, dhi=500, temp=25)
    # Same noon twice would collapse, so the clip case is a separate call.
    out = simulate_pv(pd.DataFrame([night, day]), sizes_kw=(3.0, 5.0))
    assert set(out["is_simulated"]) == {True}
    assert out["pv_ac_kw_simulated"].name.endswith("_simulated")
    night_rows = out[out["timestamp"] == pd.Timestamp("2024-06-15 00:00", tz="Asia/Colombo")]
    assert (night_rows["pv_ac_kw_simulated"] == 0).all()
    day_rows = out[out["timestamp"] == pd.Timestamp("2024-06-15 12:00", tz="Asia/Colombo")]
    ac3 = day_rows.loc[day_rows["system_kw"] == 3.0, "pv_ac_kw_simulated"].iloc[0]
    ac5 = day_rows.loc[day_rows["system_kw"] == 5.0, "pv_ac_kw_simulated"].iloc[0]
    assert ac3 > 0
    assert ac5 > ac3
    assert ac5 / ac3 == pytest.approx(5 / 3, rel=0.05)
    assert (day_rows["pv_ac_kw_simulated"] <= day_rows["system_kw"]).all()

    clipped = simulate_pv(pd.DataFrame([bright]), sizes_kw=(1.0,))
    assert clipped["pv_ac_kw_simulated"].iloc[0] == pytest.approx(1.0, abs=1e-4)
    assert clipped["inverter_ac_limit_kw"].iloc[0] == 1.0


def test_hotter_air_lowers_simulated_output():
    cool = pd.DataFrame([_weather_row("2024-06-15 12:00", ghi=700, dni=500, dhi=200, temp=25)])
    hot = pd.DataFrame([_weather_row("2024-06-15 12:00", ghi=700, dni=500, dhi=200, temp=45)])
    ac_cool = simulate_pv(cool, sizes_kw=(5.0,))["pv_ac_kw_simulated"].iloc[0]
    ac_hot = simulate_pv(hot, sizes_kw=(5.0,))["pv_ac_kw_simulated"].iloc[0]
    assert ac_hot < ac_cool
    assert ac_cool > 0


def test_missing_irradiance_stays_missing():
    row = _weather_row("2024-06-15 12:00", ghi=500, dni=300, dhi=200, temp=25)
    row["dni_wm2"] = float("nan")
    out = simulate_pv(pd.DataFrame([row]), sizes_kw=(5.0,))
    assert pd.isna(out["pv_ac_kw_simulated"].iloc[0])


def test_nasa_clip_keeps_colombo_dates_only():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-05-31 23:30",
                    "2024-06-01 00:30",
                    "2024-06-30 23:30",
                    "2024-07-01 00:30",
                ]
            ).tz_localize("Asia/Colombo"),
            "location_id": "colombo",
        }
    )
    clipped = clip_to_local_days(frame, date(2024, 6, 1), date(2024, 6, 30))
    assert list(clipped["timestamp"].dt.day) == [1, 30]
    assert list(clipped["timestamp"].dt.month) == [6, 6]


def test_slice_month_keeps_the_last_hour_and_drops_the_next_month():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-06-01 00:00", "2024-06-30 23:00", "2024-07-01 00:00"]
            ).tz_localize("Asia/Colombo"),
            "location_id": ["colombo", "colombo", "kandy"],
        }
    )
    sliced = slice_month(frame, "colombo", "2024-06")
    assert len(sliced) == 2
    assert sliced["timestamp"].max().day == 30


def test_simulate_command_writes_a_labelled_csv(tmp_path):
    from data.pipeline.cli import main

    weather = pd.DataFrame(
        [
            _weather_row("2024-06-15 00:00", ghi=0, dni=0, dhi=0, temp=26),
            _weather_row("2024-06-15 12:00", ghi=600, dni=400, dhi=200, temp=30),
        ]
    )
    weather_path = tmp_path / "weather.csv"
    write_dataset(weather, weather_path, {"pv_is_simulated": False})
    out_dir = tmp_path / "pv"
    code = main(
        [
            "simulate-pv",
            "--weather",
            str(weather_path),
            "--sizes",
            "5",
            "--out",
            str(out_dir),
        ]
    )
    assert code == 0
    written = out_dir / "open_meteo_archive" / "colombo.csv"
    assert written.is_file()
    meta = json.loads(written.with_suffix(".meta.json").read_text())
    assert meta["pv_is_simulated"] is True
    assert meta["is_measured_generation"] is False
    frame = read_weather_csv(written)
    assert "pv_ac_kw_simulated" in frame.columns
    assert frame["is_simulated"].all()
    noon = frame[frame["timestamp"] == pd.Timestamp("2024-06-15 12:00", tz="Asia/Colombo")]
    assert noon["pv_ac_kw_simulated"].iloc[0] > 0


def test_write_sample_copies_only_the_month(tmp_path):
    weather_root = tmp_path / "weather"
    pv_root = tmp_path / "pv"
    sample_dir = tmp_path / "sample"
    rows = [
        _weather_row("2024-06-15 12:00", ghi=400, dni=200, dhi=200, temp=29),
        _weather_row("2024-07-01 12:00", ghi=400, dni=200, dhi=200, temp=29),
    ]
    for source_id, kind in (
        ("open_meteo_archive", "reanalysis"),
        ("nasa_power", "satellite_model"),
        ("open_meteo_previous_day1", "forecast"),
    ):
        frame = pd.DataFrame(rows)
        frame["source"] = source_id
        frame["data_kind"] = kind
        path = weather_root / source_id / "colombo.csv"
        write_dataset(frame, path, {"source": source_id, "pv_is_simulated": False})
    pv = simulate_pv(pd.DataFrame(rows).assign(source="open_meteo_archive", data_kind="reanalysis"), sizes_kw=(5.0,))
    write_dataset(
        pv,
        pv_root / "open_meteo_archive" / "colombo.csv",
        {"pv_is_simulated": True},
    )
    written = export_month(
        month="2024-06",
        location_id="colombo",
        weather_root=weather_root,
        pv_root=pv_root,
        sample_dir=sample_dir,
    )
    assert len(written) == 4
    archive = read_weather_csv(sample_dir / "colombo_open_meteo_archive_2024-06.csv")
    assert len(archive) == 1
    assert archive["timestamp"].iloc[0].month == 6
    pv_sample = read_weather_csv(sample_dir / "colombo_pv_simulated_open_meteo_archive_2024-06.csv")
    assert len(pv_sample) == 1
    assert pv_sample["pv_ac_kw_simulated"].iloc[0] > 0
    meta = json.loads((sample_dir / "colombo_open_meteo_previous_day1_2024-06.meta.json").read_text())
    assert meta["sample"] is True
    assert meta["sample_month"] == "2024-06"


def test_write_sample_live_snapshot(tmp_path):
    snapshot = tmp_path / "live" / "colombo" / "20261103T120000Z"
    snapshot.mkdir(parents=True)
    (snapshot / "hourly.csv").write_text("timestamp,location_id\n", encoding="utf-8")
    (snapshot / "current.csv").write_text("timestamp,location_id\n", encoding="utf-8")
    (snapshot / "meta.json").write_text("{}\n", encoding="utf-8")
    sample_dir = tmp_path / "sample"
    export_live_snapshot(location_id="colombo", live_root=tmp_path / "live", sample_dir=sample_dir)
    assert (sample_dir / "colombo_live_hourly.csv").is_file()
    assert (sample_dir / "colombo_live_current.csv").is_file()
    meta = json.loads((sample_dir / "colombo_live.meta.json").read_text())
    assert meta["sample"] is True


def test_cli_help_exits_cleanly():
    from data.pipeline.cli import main

    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
