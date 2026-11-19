"""The hourly job must not leave a simulated forecast sitting on an old issue."""

from datetime import datetime

from api.jobs import run_forecast
from api.memory import MemoryStore
from api.seed_demo import DEMO_MODEL_VERSION, sites_for_forecast


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


def test_simulated_refresh_covers_demo_sim_and_other_table_sites():
    store = MemoryStore()
    store.add_site(
        "demo-sim",
        name="Demo home (SIMULATED)",
        timezone="Asia/Colombo",
        system_kw=3.0,
        latitude=6.90,
        longitude=79.86,
        demand_scale_kw=1.2,
        has_meter=True,
    )
    store.add_site(
        "home-extra",
        name="Extra",
        timezone="Asia/Colombo",
        system_kw=4.0,
        latitude=6.91,
        longitude=79.87,
        tilt_deg=12,
        azimuth_deg=90,
        demand_scale_kw=1.0,
        has_meter=True,
    )
    store.add_site("bare", timezone="Asia/Colombo")
    chosen = sites_for_forecast(store).set_index("site_id")
    assert "bare" not in chosen.index
    assert chosen.loc["demo-sim", "tilt_deg"] == 10
    assert chosen.loc["demo-sim", "azimuth_deg"] == 180
    assert chosen.loc["demo-sim", "demand_scale_kw"] == 1.2
    assert chosen.loc["demo-sim", "latitude"] == 6.90
    assert chosen.loc["home-extra", "azimuth_deg"] == 90
    assert "home-dehiwala" in chosen.index
    now = datetime.fromisoformat("2026-11-19T10:00:00+05:30")
    summary = run_forecast(store, now=now, demo_estimators=8)

    assert summary["simulated_refresh"]["data_label"] == "SIMULATED"
    by_site = {}
    for row in store.forecasts:
        by_site.setdefault(row["site_id"], []).append(row)
    assert "bare" not in by_site
    assert "home-dehiwala" in by_site
    for site_id in ("demo-sim", "home-extra"):
        rows = by_site[site_id]
        assert {row["target"] for row in rows} == {"pv", "demand", "net"}
        assert {row["data_label"] for row in rows} == {"SIMULATED"}
        assert all(row["is_simulated"] for row in rows)
        assert all(row["model_version"] == DEMO_MODEL_VERSION for row in rows)
    assert store.reading_count() == 0
    assert store.promoted_model("pv") is None
    demo = store.sites["demo-sim"]
    assert demo["name"] == "Demo home (SIMULATED)"
    assert demo["system_kw"] == 3.0


def test_a_promoted_model_is_not_replaced_by_the_demo_refresh():
    store = MemoryStore()
    store.insert_model("real-pv", "pv", {"test": {"mae_kw": 0.2}}, promoted=True, artefact_url=None, git_sha=None)
    store.add_site("home-a", timezone="Asia/Colombo", system_kw=3)
    summary = run_forecast(store, demo_estimators=8)
    assert "simulated_refresh" not in summary
    assert store.promoted_model("pv")["version"] == "real-pv"
    assert all(row["model_version"] != DEMO_MODEL_VERSION for row in store.forecasts)
