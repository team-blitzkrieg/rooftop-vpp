"""The demo seed writes a simulated forecast and does not promote a model."""

from datetime import datetime

from api.memory import MemoryStore
from api.seed_demo import DEMO_MODEL_VERSION, DEMO_SITES, HORIZON_HOURS, seed_store


def test_seed_is_idempotent_and_does_not_promote():
    store = MemoryStore()
    store.add_site("home-dehiwala", name="Already there", timezone="Asia/Colombo", system_kw=5.0)
    store.insert_model(
        "real-pv",
        "pv",
        {"test": {"mae_kw": 0.2}},
        promoted=True,
        artefact_url=None,
        git_sha=None,
    )
    now = datetime.fromisoformat("2024-07-15T09:40:00+05:30")
    first = seed_store(store, now=now, n_estimators=15, history_days=21)
    second = seed_store(store, now=now, n_estimators=15, history_days=21)

    assert store.sites["home-dehiwala"]["name"] == "Already there"
    assert set(DEMO_SITES) <= set(store.sites)
    assert first["inserted_sites"] == ["demo-sim", "home-moratuwa", "home-nugegoda"]
    assert second["inserted_sites"] == []
    assert store.reading_count() == 0
    assert store.promoted_model("pv")["version"] == "real-pv"
    assert store.promoted_model("demand") is None
    assert all(row["version"] != DEMO_MODEL_VERSION for row in store.models)
    assert all(row["promoted"] is False or row["version"] == "real-pv" for row in store.models)

    demo = [row for row in store.forecasts if row["model_version"] == DEMO_MODEL_VERSION]
    assert len(demo) == len(DEMO_SITES) * 3 * HORIZON_HOURS
    assert {row["target"] for row in demo} == {"pv", "demand", "net"}
    assert {row["data_label"] for row in demo} == {"SIMULATED"}
    assert all(row["is_simulated"] for row in demo)
    assert first["rows"] == second["rows"] == len(demo)
    assert len([row for row in store.runs if row["model_version"] == DEMO_MODEL_VERSION]) == len(DEMO_SITES) * 3
