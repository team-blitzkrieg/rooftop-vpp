"""Fault check uses stored readings and does not invent a settings pass."""

from datetime import datetime, timedelta, timezone

from api.fault_job import run_fault_check
from api.memory import MemoryStore


def _forecast(store, site_id, start, values):
    run_id = store.record_run(site_id, "pv", "success", issued_at=start, model_version="demo")
    rows = []
    for hour, (value, baseline) in enumerate(values):
        stamp = start + timedelta(hours=hour)
        rows.append(
            {
                "timestamp": stamp.isoformat(),
                "issued_at": start.isoformat(),
                "lead_hours": hour,
                "value_kw": value,
                "baseline_kw": baseline,
                "net_kw": None,
                "resolution": "hourly",
                "data_label": "SIMULATED",
                "is_simulated": True,
            }
        )
    store.publish_forecast(
        site_id,
        "pv",
        start.isoformat(),
        rows,
        model_version="demo",
        run_id=run_id,
        resolution="hourly",
        data_label="SIMULATED",
        is_simulated=True,
    )


def test_no_readings_stays_not_read_and_insufficient():
    store = MemoryStore()
    store.add_site("home-a", system_kw=3)
    summary = run_fault_check(store, now=datetime(2026, 11, 17, tzinfo=timezone.utc))
    by_rule = {row["rule"]: row for row in summary["results"]}
    assert by_rule["settings"]["status"] == "not_read"
    assert by_rule["underperformance"]["status"] == "insufficient"
    assert by_rule["settings"]["data_label"] == "NOT_AVAILABLE"


def test_low_simulated_readings_can_alert_without_a_settings_pass():
    store = MemoryStore()
    store.add_site("home-a", system_kw=3)
    start = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    # Three sunny days: expected is high, actual is far below.
    values = []
    for day in range(3):
        for hour in range(24):
            sunny = 10 <= hour <= 14
            values.append((0.2 if sunny else 0.0, 2.5 if sunny else 0.1))
    _forecast(store, "home-a", start, values)
    for day in range(3):
        for hour in range(24):
            stamp = start + timedelta(days=day, hours=hour)
            sunny = 10 <= hour <= 14
            store.upsert_reading(
                "home-a",
                stamp,
                pv_kw=0.2 if sunny else 0.0,
                data_label="SIMULATED",
                is_simulated=True,
            )
    summary = run_fault_check(store, now=start + timedelta(days=4))
    by_rule = {row["rule"]: row for row in summary["results"]}
    assert by_rule["settings"]["status"] == "not_read"
    assert by_rule["underperformance"]["status"] == "alert"
    assert by_rule["underperformance"]["is_simulated"] is True
    assert by_rule["underperformance"]["data_label"] == "SIMULATED"
