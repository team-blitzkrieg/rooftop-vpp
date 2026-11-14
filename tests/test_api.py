"""API tests. No database and no network."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from api.jobs import main, run_forecast, run_retrain
from api.memory import MemoryStore
from api.util import should_promote


def _client(store=None):
    app = create_app(store or MemoryStore())
    return TestClient(app), app.state.store


def _seed_forecast(store, *, issued, value=1.25, status="success"):
    store.add_site("home-a")
    run_id = store.record_run(
        "home-a",
        "demand",
        status,
        issued_at=issued,
        model_version="demand-lgbm-test",
    )
    if status == "success":
        store.publish_forecast(
            "home-a",
            "demand",
            issued,
            [
                {
                    "timestamp": issued + timedelta(hours=19),
                    "value_kw": value,
                    "baseline_kw": 1.0,
                    "net_kw": 0.4,
                    "lead_hours": 19,
                }
            ],
            model_version="demand-lgbm-test",
            run_id=run_id,
            resolution="hourly",
            data_label="SIMULATED",
            is_simulated=True,
        )


def test_unknown_device_key_is_rejected_and_stores_nothing():
    client, store = _client()
    store.add_device("meter-1", "home-a", "the-real-key")
    bad = client.post(
        "/ingest",
        headers={"X-Device-Key": "nope"},
        json={"timestamp": "2024-06-01T19:00:00+05:30", "consumption_kw": 0.8},
    )
    assert bad.status_code == 401
    assert store.reading_count() == 0
    missing = client.post(
        "/ingest",
        json={"timestamp": "2024-06-01T19:00:00+05:30", "consumption_kw": 0.8},
    )
    assert missing.status_code == 401
    assert store.reading_count() == 0


def test_ingest_writes_a_reading():
    client, store = _client()
    store.add_device("meter-1", "home-a", "the-real-key")
    response = client.post(
        "/ingest",
        headers={"X-Device-Key": "the-real-key"},
        json={"timestamp": "2024-06-01T19:00:00+05:30", "consumption_kw": 0.8},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["site_id"] == "home-a"
    assert body["controls_equipment"] is False
    assert store.reading_count("home-a") == 1


def test_stale_forecast_is_flagged_and_a_failed_run_keeps_it():
    store = MemoryStore()
    issued = datetime.now(timezone.utc) - timedelta(days=3)
    _seed_forecast(store, issued=issued, value=1.25)
    store.record_run(
        "home-a",
        "demand",
        "failed",
        issued_at=datetime.now(timezone.utc),
        model_version="demand-lgbm-test",
        message="weather fetch failed",
    )
    client, _ = _client(store)
    response = client.get("/forecasts/home-a", params={"target": "demand"})
    assert response.status_code == 200
    body = response.json()
    assert body["stale"] is True
    assert body["using_previous"] is True
    assert body["controls_equipment"] is False
    assert body["data_label"] == "SIMULATED"
    assert body["rows"][0]["value_kw"] == 1.25
    assert body["message"] == "weather fetch failed"


def test_openapi_has_no_equipment_command():
    client, _ = _client()
    spec = client.get("/openapi.json").json()
    paths = " ".join(spec["paths"])
    assert "ingest" in paths
    assert "forecasts" in paths
    for word in ("setpoint", "modbus", "websocket", "control"):
        assert word not in paths
    dumped = json.dumps(spec["paths"])
    assert "command" not in dumped


def test_reads_can_require_a_key_and_promote_needs_an_admin_key(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    monkeypatch.setenv("READ_API_KEY", "reader")
    store = MemoryStore()
    issued = datetime.now(timezone.utc) - timedelta(hours=1)
    _seed_forecast(store, issued=issued)
    client, _ = _client(store)
    assert client.get("/forecasts/home-a", params={"target": "demand"}).status_code == 401
    ok = client.get(
        "/forecasts/home-a",
        params={"target": "demand"},
        headers={"X-Read-Key": "reader"},
    )
    assert ok.status_code == 200
    assert ok.json()["stale"] is False
    assert client.post("/models", json={"version": "v", "target": "pv"}).status_code == 503
    monkeypatch.setenv("ADMIN_API_KEY", "admin")
    denied = client.post(
        "/models",
        json={"version": "demand-lgbm-new", "target": "demand", "mae_kw": 0.05},
    )
    assert denied.status_code == 401
    promoted = client.post(
        "/models",
        headers={"X-Admin-Key": "admin"},
        json={
            "version": "demand-lgbm-new",
            "target": "demand",
            "mae_kw": 0.05,
            "metrics": {"test": {"overall": {"lightgbm": {"mae_kw": 0.05}}}},
        },
    )
    assert promoted.status_code == 200
    assert promoted.json()["promoted"] is True
    kept = client.post(
        "/models",
        headers={"X-Admin-Key": "admin"},
        json={"version": "demand-lgbm-worse", "target": "demand", "mae_kw": 1.0},
    )
    assert kept.json()["promoted"] is False
    assert store.promoted_model("demand")["version"] == "demand-lgbm-new"


def test_jobs_skip_without_a_database_and_keep_the_promoted_model(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["forecast"]) == 0
    assert "DATABASE_URL is not set" in capsys.readouterr().out

    store = MemoryStore()
    result = run_retrain(store)
    assert result["status"] == "skipped"
    assert store.promoted_model("demand") is None

    store.insert_model(
        "demand-lgbm-old",
        "demand",
        {"test": {"overall": {"lightgbm": {"mae_kw": 0.2}}}},
        promoted=True,
        artefact_url=None,
        git_sha="old",
    )
    for day in (1, 2, 3):
        store.upsert_reading(
            "home-a",
            f"2026-11-0{day}T12:00:00+05:30",
            consumption_kw=0.5,
        )

    def trainer(store, *, allow_synthetic):
        return {
            "forecast_target": "demand",
            "model_version": "demand-lgbm-worse",
            "metrics": {"test": {"overall": {"lightgbm": {"mae_kw": 0.4}}}},
            "git_sha": "new",
        }

    worse = run_retrain(store, trainer=trainer)
    assert worse["models"][0]["promoted"] is False
    assert store.promoted_model("demand")["version"] == "demand-lgbm-old"

    def better(store, *, allow_synthetic):
        return {
            "forecast_target": "demand",
            "model_version": "demand-lgbm-better",
            "metrics": {"test": {"overall": {"lightgbm": {"mae_kw": 0.1}}}},
            "git_sha": "new",
        }

    improved = run_retrain(store, trainer=better)
    assert improved["models"][0]["promoted"] is True
    assert store.promoted_model("demand")["version"] == "demand-lgbm-better"


def test_a_failed_hourly_run_does_not_delete_the_last_forecast():
    store = MemoryStore()
    issued = datetime.now(timezone.utc) - timedelta(hours=2)
    _seed_forecast(store, issued=issued, value=0.7)
    store.insert_model(
        "demand-lgbm-missing",
        "demand",
        {"test": {"overall": {"lightgbm": {"mae_kw": 0.2}}}},
        promoted=True,
        artefact_url=None,
        git_sha=None,
    )
    summary = run_forecast(store)
    failed = [item for item in summary["targets"] if item.get("status") == "failed"]
    assert failed
    kept = store.latest_success("home-a", "demand")
    assert kept["rows"][0]["value_kw"] == 0.7
    assert kept["model_version"] == "demand-lgbm-test"


def test_should_promote_only_when_mae_improves():
    assert should_promote(0.2, None) is True
    assert should_promote(0.2, 0.3) is True
    assert should_promote(0.3, 0.2) is False
    assert should_promote(None, 0.2) is False
    assert should_promote(0.2, 0.2) is False
