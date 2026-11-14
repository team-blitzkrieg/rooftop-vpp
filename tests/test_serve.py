"""Serving tests. No database server and no network."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from fastapi.testclient import TestClient

from forecasting.config import EXAMPLE_SITES, TIMEZONE
from forecasting.synthetic import generate_simulated
from forecasting.tables import load_sites
from serve.app import create_app
from serve.jobs import run_forecast, run_retrain
from serve.memory import MemoryStore
from serve.models import add_simulated_consumption
from serve.mqtt import parse_payload
from serve.registry import should_promote


def _bundle(tmp_path):
    sites = load_sites(EXAMPLE_SITES)
    sites = sites.loc[sites["site_id"] == "home-dehiwala"].copy()
    readings, weather = generate_simulated(
        sites,
        date(2024, 6, 1),
        date(2024, 6, 14),
        "hourly",
        seed=7,
    )
    readings = add_simulated_consumption(readings, weather, seed=7)
    store = MemoryStore()
    store.upsert_site(sites.iloc[0].to_dict())
    store.add_device("meter-home-dehiwala", "home-dehiwala", "device-secret")
    for row in readings.itertuples(index=False):
        store.upsert_reading(
            "home-dehiwala",
            row.timestamp,
            pv_kw=float(row.pv_kw),
            consumption_kw=float(row.consumption_kw),
            data_label="SIMULATED",
            is_simulated=True,
        )
    tracking = f"sqlite:///{tmp_path / 'mlflow.db'}"
    trained = run_retrain(store, weather=weather, tracking_uri=tracking, rounds=30, promote_initial=True)
    return store, weather, tracking, trained


def test_should_promote_only_when_both_comparisons_improve():
    assert should_promote(0.2, 0.3, None) is True
    assert should_promote(0.2, 0.3, 0.25) is True
    assert should_promote(0.4, 0.3, None) is False
    assert should_promote(0.22, 0.3, 0.2) is False
    assert should_promote(None, 0.3, 0.2) is False


def test_mqtt_payload_requires_a_token_and_a_time():
    body = parse_payload(
        b'{"device_token":"abc","timestamp":"2024-06-01T01:00:00+05:30","pv_kw":0.1}'
    )
    assert body["device_token"] == "abc"
    try:
        parse_payload(b'{"pv_kw": 1}')
    except ValueError as exc:
        assert "timestamp" in str(exc)
    else:
        raise AssertionError("expected a timestamp error")


def test_ingest_rejects_a_missing_or_unknown_device_token():
    store = MemoryStore()
    store.add_device("meter-1", "home-dehiwala", "device-secret")
    client = TestClient(create_app(store))
    missing = client.post("/ingest", json={"timestamp": "2024-06-01T01:00:00+05:30", "pv_kw": 0.2})
    assert missing.status_code == 401
    bad = client.post(
        "/ingest",
        headers={"X-Device-Token": "nope"},
        json={"timestamp": "2024-06-01T01:00:00+05:30", "pv_kw": 0.2},
    )
    assert bad.status_code == 401
    assert store.readings("home-dehiwala") == []
    ok = client.post(
        "/ingest",
        headers={"X-Device-Token": "device-secret"},
        json={"timestamp": "2024-06-01T01:00:00+05:30", "pv_kw": 0.2, "consumption_kw": 0.4},
    )
    assert ok.status_code == 200
    assert ok.json()["controls_equipment"] is False
    assert len(store.readings("home-dehiwala")) == 1


def test_worker_writes_a_registry_forecast_and_a_failure_keeps_it(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "front-door")
    monkeypatch.setenv("STALE_AFTER_MINUTES", "120")
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    store, weather, tracking, trained = _bundle(tmp_path)
    assert all(item["promoted"] for item in trained["models"])
    issued = pd.Timestamp("2024-06-14 00:00", tz=TIMEZONE)
    result = run_forecast(
        store,
        now=issued.to_pydatetime(),
        weather_for=lambda site, moment: weather,
        tracking_uri=tracking,
    )
    assert result["sites"][0]["status"] == "success"
    client = TestClient(create_app(store))
    denied = client.get("/forecast/home-dehiwala", params={"target": "pv"})
    assert denied.status_code == 401
    headers = {"X-API-Key": "front-door"}
    for target in ("pv", "demand", "net"):
        response = client.get("/forecast/home-dehiwala", params={"target": target}, headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["controls_equipment"] is False
        assert body["data_label"] == "SIMULATED"
        assert body["model_version"]
        assert body["using_previous"] is False
        assert len(body["rows"]) == 24
        if target == "pv":
            assert min(row["value_kw"] for row in body["rows"]) >= 0
    spec = client.get("/openapi.json").json()
    paths = " ".join(spec["paths"])
    for word in ("setpoint", "modbus", "websocket", "control"):
        assert word not in paths

    def boom(site, moment):
        raise RuntimeError("weather down")

    failed = run_forecast(
        store,
        now=issued.to_pydatetime(),
        weather_for=boom,
        tracking_uri=tracking,
    )
    assert failed["sites"][0]["status"] == "failed"
    kept = client.get("/forecast/home-dehiwala", params={"target": "demand"}, headers=headers)
    assert kept.status_code == 200
    body = kept.json()
    assert body["using_previous"] is True
    assert len(body["rows"]) == 24
    assert body["message"] == "weather down"

    sites = client.get("/sites", headers=headers)
    assert sites.status_code == 200
    assert sites.json()["sites"][0]["site_id"] == "home-dehiwala"
    readings = client.get("/readings/home-dehiwala", headers=headers)
    assert readings.status_code == 200
    assert readings.json()["rows"]
    events = client.get(
        "/forecast/home-dehiwala/events",
        params={"target": "pv", "once": 1},
        headers=headers,
    )
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "data:" in events.text
    assert client.post("/jobs/forecast").status_code == 503


def test_a_worse_retrain_does_not_move_production(tmp_path):
    store, weather, tracking, trained = _bundle(tmp_path)
    first = {item["target"]: item["version"] for item in trained["models"]}
    again = run_retrain(store, weather=weather, tracking_uri=tracking, rounds=5, promote_initial=False)
    for item in again["models"]:
        if item.get("promoted"):
            assert item["holdout_mae"] < trained["models"][0]["holdout_mae"] or item["version"] != first[item["target"]]
        else:
            from serve.registry import production_version

            assert str(production_version(item["target"], tracking).version) == str(first[item["target"]])


def test_stale_flag_follows_the_issue_time(monkeypatch):
    monkeypatch.setenv("STALE_AFTER_MINUTES", "60")
    monkeypatch.setenv("API_KEY", "")
    store = MemoryStore()
    store.upsert_site({"site_id": "home-dehiwala", "system_kw": 5})
    issued = datetime.now(timezone.utc) - timedelta(hours=3)
    store.publish_success(
        "home-dehiwala",
        "pv",
        issued,
        [{"timestamp": issued, "value_kw": 1.5}],
        model_version="1",
        data_label="SIMULATED",
        is_simulated=True,
    )
    client = TestClient(create_app(store))
    body = client.get("/forecast/home-dehiwala", params={"target": "pv"}).json()
    assert body["stale"] is True
    assert body["rows"][0]["value_kw"] == 1.5
    assert json.loads(json.dumps(body))["controls_equipment"] is False
