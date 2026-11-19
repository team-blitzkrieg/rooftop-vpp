"""The hourly job must not leave a simulated forecast sitting on an old issue."""

from datetime import datetime

from api.jobs import run_forecast
from api.memory import MemoryStore
from api.seed_demo import DEMO_MODEL_VERSION


def test_unpromoted_forecast_is_refreshed_and_stays_simulated():
    store = MemoryStore()
    now = datetime.fromisoformat("2026-11-17T16:00:00+05:30")
    summary = run_forecast(store, now=now, demo_estimators=8)

    refresh = summary["simulated_refresh"]
    assert refresh["data_label"] == "SIMULATED"
    assert refresh["model_version"] == DEMO_MODEL_VERSION
    assert refresh["issued_at"].startswith("2026-11-17T16:00:00")
    assert store.promoted_model("pv") is None
    assert store.promoted_model("demand") is None
    assert store.reading_count() == 0
    labels = {row["data_label"] for row in store.forecasts}
    assert labels == {"SIMULATED"}
    assert all(row["is_simulated"] for row in store.forecasts)


def test_a_promoted_model_is_not_replaced_by_the_demo_refresh():
    store = MemoryStore()
    store.insert_model("real-pv", "pv", {"test": {"mae_kw": 0.2}}, promoted=True, artefact_url=None, git_sha=None)
    store.add_site("home-a", timezone="Asia/Colombo", system_kw=3)
    summary = run_forecast(store, demo_estimators=8)
    assert "simulated_refresh" not in summary
    assert store.promoted_model("pv")["version"] == "real-pv"
    assert all(row["model_version"] != DEMO_MODEL_VERSION for row in store.forecasts)
