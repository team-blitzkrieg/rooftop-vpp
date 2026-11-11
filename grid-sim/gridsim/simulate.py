"""Run the 50-home neighbourhood for a year, with and without control.

Three cases per scenario:

* ``no_control``  every inverter exports all it can (today's behaviour).
* ``limit``       a learned voltage model picks one fair export limit for all
                  solar homes each hour, so that no home goes over the voltage
                  limit and the transformer stays inside its rating.
* ``limit_store`` the same, but homes with a battery store the energy that
                  would be held back and release it from 17:30 to 21:30.

The limit is the same share of system size for every home. That is the
"fair share" rule: nobody is cut off because they are at the end of the line.

Everything here is simulated. See ``README.md`` for the assumptions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import demand
from .feeder import V_LOWER_PU, V_UPPER_PU, Feeder, FeederConfig

ROOT = Path(__file__).resolve().parents[2]
PV_SIZES_KW = (3.0, 5.0, 10.0)
PV_SIZE_PROBABILITY = (0.3, 0.5, 0.2)
EVENING_HOURS = (18, 19, 20, 21)  # hourly stand-in for the 17:30-21:30 window


@dataclass(frozen=True)
class Scenario:
    solar_share: float = 0.6  # share of the 50 homes that have rooftop solar
    year: int = 2025
    location: str = "colombo"
    pv_source: str = "open_meteo_archive"
    ev_share: float = 0.1
    battery_share: float = 0.3  # share of solar homes with a battery (limit_store case)
    battery_kwh: float = 5.0
    battery_kw: float = 2.5
    battery_efficiency: float = 0.9  # round trip
    v_target_pu: float = 1.05  # the controller aims here, 0.01 below the 1.06 limit
    trafo_target_pct: float = 95.0
    train_until_month: int = 8  # voltage model: train Jan-Aug, test Sep-Dec
    seed: int = 7
    feeder: FeederConfig = field(default_factory=FeederConfig)


def load_pv_per_kw(scenario: Scenario) -> pd.Series:
    """Hourly AC output per kW of system size, from the repo's simulated PV table."""
    path = ROOT / "data" / "processed" / "pv_simulated" / scenario.pv_source / f"{scenario.location}.csv"
    frame = pd.read_csv(path, usecols=["timestamp", "system_kw", "pv_ac_kw_simulated"])
    frame = frame[frame["system_kw"] == 5.0]
    index = pd.to_datetime(frame["timestamp"]).dt.tz_localize(None).dt.floor("h")
    series = pd.Series(frame["pv_ac_kw_simulated"].to_numpy() / 5.0, index=index)
    return series.loc[str(scenario.year)]


def build_homes(scenario: Scenario) -> dict:
    """Decide which homes have solar, an EV or a battery. Fixed by the seed."""
    rng = np.random.default_rng(scenario.seed)
    n = scenario.feeder.n_homes
    order = rng.permutation(n)
    # Nested: the homes with solar at 40% also have it at 60%, so shares compare fairly.
    sizes = rng.choice(PV_SIZES_KW, n, p=PV_SIZE_PROBABILITY)
    has_solar = np.zeros(n, bool)
    has_solar[order[: round(scenario.solar_share * n)]] = True
    ev_order = rng.permutation(n)
    has_ev = np.zeros(n, bool)
    has_ev[ev_order[: round(scenario.ev_share * n)]] = True
    battery_order = rng.permutation(n)
    solar_first = [h for h in battery_order if has_solar[h]]
    has_battery = np.zeros(n, bool)
    has_battery[solar_first[: round(scenario.battery_share * has_solar.sum())]] = True
    return {
        "pv_kw_rated": np.where(has_solar, sizes, 0.0),
        "has_solar": has_solar,
        "has_ev": has_ev,
        "has_battery": has_battery,
        "rng": rng,
    }


class VoltageModel:
    """Learned stand-in for the network: home voltages and transformer flow
    as straight-line functions of each home's net power.

    v_home = a + S @ net_kw. Fitted by ridge regression on past hours.
    It uses only quantities an Edge Unit fleet could measure: each home's
    power and voltage, and the transformer flow.
    """

    def __init__(self, ridge: float = 1e-3):
        self.ridge = ridge

    def fit(self, net_kw: np.ndarray, home_v: np.ndarray, trafo_kw: np.ndarray) -> "VoltageModel":
        x = np.hstack([np.ones((len(net_kw), 1)), net_kw])
        penalty = self.ridge * np.eye(x.shape[1])
        penalty[0, 0] = 0.0
        targets = np.hstack([home_v, trafo_kw[:, None]])
        beta = np.linalg.solve(x.T @ x + penalty, x.T @ targets)
        self.v_intercept, self.v_slope = beta[0, :-1], beta[1:, :-1].T
        self.t_intercept, self.t_slope = beta[0, -1], beta[1:, -1]
        return self

    def predict(self, net_kw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return (
            self.v_intercept + net_kw @ self.v_slope.T,
            self.t_intercept + net_kw @ self.t_slope,
        )

    def export_limit(self, load_kw, pv_kw, v_target_pu, trafo_limit_kw) -> float:
        """Largest share of available solar (0 to 1) that keeps the predictions in limits."""
        v_no_pv = self.v_intercept - self.v_slope @ load_kw
        v_per_share = self.v_slope @ pv_kw
        shares = [1.0]
        rising = v_per_share > 1e-9
        if rising.any():
            shares.append(float(((v_target_pu - v_no_pv[rising]) / v_per_share[rising]).min()))
        # transformer flow is negative when the neighbourhood exports
        t_no_pv = self.t_intercept - self.t_slope @ load_kw
        t_per_share = self.t_slope @ pv_kw
        if t_per_share < -1e-9:
            shares.append(float((-trafo_limit_kw - t_no_pv) / t_per_share))
        return float(np.clip(min(shares), 0.0, 1.0))


def _record(solution: dict, pv_available, pv_used, stored=0.0, discharged=0.0, share=1.0) -> dict:
    home_v = solution["home_v_pu"]
    return {
        "v_max_pu": solution["v_max_pu"],
        "v_min_pu": solution["v_min_pu"],
        "homes_over_v": int((home_v > V_UPPER_PU).sum()),
        "trafo_loading_pct": solution["trafo_loading_pct"],
        "trafo_p_kw": solution["trafo_p_kw"],
        "pv_available_kw": float(pv_available.sum()),
        "pv_used_kw": float(pv_used.sum()),
        "stored_kw": float(stored),
        "discharged_kw": float(discharged),
        "export_share": share,
    }


def run_scenario(scenario: Scenario, per_kw: pd.Series | None = None) -> dict:
    """Return hourly tables for the three cases, the summary rows and the model test.

    ``per_kw`` (hourly output per kW of system size) can be passed in for tests.
    """
    homes = build_homes(scenario)
    per_kw = load_pv_per_kw(scenario) if per_kw is None else per_kw
    index = per_kw.index
    load = demand.home_demand_kw(index, homes["has_solar"], homes["has_ev"], homes["rng"])
    pv = per_kw.to_numpy()[:, None] * homes["pv_kw_rated"][None, :]
    feeder = Feeder(scenario.feeder)
    n_hours = len(index)
    trafo_limit_kw = scenario.trafo_target_pct / 100.0 * scenario.feeder.transformer_kva * 0.98

    # Case 1: no control. Also the training data for the voltage model.
    base, base_v = [], np.empty((n_hours, scenario.feeder.n_homes))
    for t in range(n_hours):
        solution = feeder.solve(load[t], pv[t])
        base_v[t] = solution["home_v_pu"]
        base.append(_record(solution, pv[t], pv[t]))
    base = pd.DataFrame(base, index=index)

    train = index.month <= scenario.train_until_month
    net_kw = pv - load
    model = VoltageModel().fit(net_kw[train], base_v[train], base["trafo_p_kw"].to_numpy()[train])
    predicted_v, predicted_t = model.predict(net_kw[~train])
    model_test = {
        "train_hours": int(train.sum()),
        "test_hours": int((~train).sum()),
        "voltage_mae_volts": float(np.abs(predicted_v - base_v[~train]).mean() * 230.0),
        "voltage_max_error_volts": float(np.abs(predicted_v - base_v[~train]).max() * 230.0),
        "transformer_mae_kw": float(np.abs(predicted_t - base["trafo_p_kw"].to_numpy()[~train]).mean()),
    }

    # Cases 2 and 3: the controller acts only in the test months it has not seen.
    def controlled(with_storage: bool) -> pd.DataFrame:
        rows = base.to_dict("records")
        battery = homes["has_battery"] if with_storage else np.zeros_like(homes["has_battery"])
        soc = np.zeros(scenario.feeder.n_homes)
        one_way = scenario.battery_efficiency**0.5
        for t in np.flatnonzero(~train):
            hour = index[t].hour
            discharge = np.zeros_like(soc)
            if hour in EVENING_HOURS and soc.sum() > 0:
                hours_left = EVENING_HOURS[-1] - hour + 1
                discharge = np.minimum(soc / hours_left, scenario.battery_kw)
                soc -= discharge
            share = 1.0
            if pv[t].sum() > 0:
                share = model.export_limit(load[t], pv[t], scenario.v_target_pu, trafo_limit_kw)
            held_back = (1.0 - share) * pv[t]
            charge = np.where(battery, np.minimum(held_back, scenario.battery_kw), 0.0)
            charge = np.minimum(charge, (scenario.battery_kwh - soc) / one_way)
            soc += charge * one_way
            if share >= 1.0 and not discharge.any():
                continue  # nothing changed, the no-control hour stands
            exported = share * pv[t] + discharge * one_way
            solution = feeder.solve(load[t], exported)
            rows[t] = _record(
                solution, pv[t], share * pv[t] + charge, charge.sum(),
                (discharge * one_way).sum(), share,
            )
        return pd.DataFrame(rows, index=index)

    cases = {"no_control": base, "limit": controlled(False), "limit_store": controlled(True)}
    test_mask = ~train
    summary = []
    for name, table in cases.items():
        for period, mask in (("full_year", np.ones(n_hours, bool)), ("test_months", test_mask)):
            if name != "no_control" and period == "full_year":
                continue  # the controller only ran in the test months
            part = table[mask]
            available = part["pv_available_kw"].sum()
            lost = available - part["pv_used_kw"].sum()
            summary.append(
                {
                    "solar_share": scenario.solar_share,
                    "homes_with_solar": int(homes["has_solar"].sum()),
                    "solar_kw_installed": float(homes["pv_kw_rated"].sum()),
                    "case": name,
                    "period": period,
                    "hours": int(mask.sum()),
                    "transformer_overload_hours": int((part["trafo_loading_pct"] > 100).sum()),
                    "transformer_max_loading_pct": round(float(part["trafo_loading_pct"].max()), 1),
                    "over_voltage_hours": int((part["v_max_pu"] > V_UPPER_PU).sum()),
                    "home_hours_over_voltage": int(part["homes_over_v"].sum()),
                    "under_voltage_hours": int((part["v_min_pu"] < V_LOWER_PU).sum()),
                    "max_voltage_v": round(float(part["v_max_pu"].max() * 230.0), 1),
                    "min_voltage_v": round(float(part["v_min_pu"].min() * 230.0), 1),
                    "solar_available_kwh": round(float(available)),
                    "solar_held_back_kwh": round(float(lost)),
                    "solar_held_back_pct": round(float(100 * lost / available), 2) if available else 0.0,
                    "stored_kwh": round(float(part["stored_kw"].sum())),
                    "evening_peak_import_kw": round(
                        float(part.loc[part.index.hour.isin(EVENING_HOURS), "trafo_p_kw"].max()), 1
                    ),
                }
            )
    return {
        "scenario": asdict(scenario),
        "homes": {k: v.tolist() for k, v in homes.items() if k != "rng"},
        "cases": cases,
        "summary": summary,
        "model_test": model_test | {"solar_share": scenario.solar_share},
    }
