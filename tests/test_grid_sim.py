"""Grid-simulation tests. Small made-up cases, no data files needed."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "grid-sim"))

from gridsim import demand  # noqa: E402
from gridsim.feeder import Feeder, FeederConfig  # noqa: E402
from gridsim.simulate import Scenario, build_homes, run_scenario  # noqa: E402


def test_feeder_has_50_homes_on_two_lines():
    feeder = Feeder()
    assert len(feeder.home_bus) == 50
    assert len(feeder.net.trafo) == 1
    assert len(feeder.net.line) == 26


def test_solar_raises_voltage_and_load_lowers_it():
    feeder = Feeder()
    idle = feeder.solve(np.zeros(50), np.zeros(50))
    sunny = feeder.solve(np.zeros(50), np.full(50, 3.0))
    evening = feeder.solve(np.full(50, 1.5), np.zeros(50))
    assert sunny["v_max_pu"] > idle["v_max_pu"] > evening["v_min_pu"]
    assert sunny["trafo_p_kw"] < 0 < evening["trafo_p_kw"]
    assert sunny["trafo_loading_pct"] > 100  # 150 kW through a 100 kVA transformer


def test_demand_shape_and_label():
    assert np.isclose(demand.daily_shape().sum(), 1.0)
    assert np.isclose(demand.daily_shape(weekend=True).sum(), 1.0)
    assert demand.daily_shape().argmax() == 19
    assert "Simulated" in demand.ASSUMPTIONS["label"]
    index = pd.date_range("2025-01-01", periods=24 * 28, freq="h")
    kw = demand.home_demand_kw(index, np.ones(200, bool), np.zeros(200, bool), np.random.default_rng(1))
    assert 9.0 < kw.sum(axis=0).mean() / 28 < 11.0


def test_solar_homes_are_nested_across_shares():
    low = build_homes(Scenario(solar_share=0.4))["has_solar"]
    high = build_homes(Scenario(solar_share=0.6))["has_solar"]
    assert low.sum() == 20 and high.sum() == 30
    assert (high | ~low).all()


def test_export_limit_removes_over_voltage_in_a_short_run():
    index = pd.date_range("2025-08-18", periods=24 * 28, freq="h")  # 2 weeks train, 2 weeks test
    per_kw = pd.Series(np.clip(np.sin((index.hour - 6) / 12 * np.pi), 0, None) * 0.8, index=index)
    result = run_scenario(Scenario(solar_share=0.8), per_kw)
    rows = {(r["case"], r["period"]): r for r in result["summary"]}
    before = rows[("no_control", "test_months")]
    after = rows[("limit", "test_months")]
    stored = rows[("limit_store", "test_months")]
    assert before["over_voltage_hours"] > 0
    assert after["over_voltage_hours"] == 0
    assert after["transformer_overload_hours"] == 0
    assert 0 < stored["solar_held_back_kwh"] < after["solar_held_back_kwh"]
    assert result["model_test"]["voltage_mae_volts"] < 1.0
