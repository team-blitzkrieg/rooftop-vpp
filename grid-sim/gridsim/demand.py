"""Synthetic household demand. SIMULATED, not measured.

There is no measured Sri Lankan household load data in this project yet.
This module makes a labelled stand-in: one daily shape with a morning bump
and an evening peak, scaled per home, with random hour-to-hour variation.
Every number here is an assumption. They are listed in ASSUMPTIONS and
written into the metadata of each results file.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Share of a day's energy used in each hour, 00:00 to 23:00. Sums to 1.
WEEKDAY_SHAPE = np.array(
    [0.022, 0.020, 0.019, 0.019, 0.022, 0.035, 0.048, 0.045, 0.036, 0.032, 0.032, 0.034,
     0.038, 0.036, 0.033, 0.033, 0.036, 0.045, 0.065, 0.082, 0.080, 0.068, 0.050, 0.032]
)
WEEKDAY_SHAPE = WEEKDAY_SHAPE / WEEKDAY_SHAPE.sum()
# Weekend: 15% more use from 09:00 to 16:00, same daily total.
WEEKEND_SHAPE = WEEKDAY_SHAPE * np.where((np.arange(24) >= 9) & (np.arange(24) <= 16), 1.15, 1.0)
WEEKEND_SHAPE = WEEKEND_SHAPE / WEEKEND_SHAPE.sum()

ASSUMPTIONS = {
    "label": "Simulated household demand. Not measured.",
    "daily_kwh_home_with_solar": 10.0,
    "daily_kwh_home_without_solar": 4.0,
    "home_to_home_spread": "lognormal, sigma 0.35, fixed per home",
    "hour_to_hour_noise": "lognormal, sigma 0.25, independent per home and hour",
    "shape": "morning bump 05:00-08:00, evening peak 18:00-22:00 with the top at 19:00-20:00",
    "weekend": "15% more use 09:00-16:00, same daily total",
    "power_factor": 0.95,
    "ev_charger_kw": 3.7,
    "ev_charge_hours": 2,
    "ev_start_hour": "random each evening, 18:00 to 21:00",
    "basis": "Team estimate. 10 kWh/day is about 300 units a month, 4 kWh/day about 120. "
    "To be replaced by utility data or pilot readings.",
}


def daily_shape(weekend: bool = False) -> np.ndarray:
    return WEEKEND_SHAPE if weekend else WEEKDAY_SHAPE


def home_demand_kw(
    index: pd.DatetimeIndex,
    has_solar: np.ndarray,
    has_ev: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Hourly demand in kW, shape (hours, homes). EV charging is included."""
    n_homes = len(has_solar)
    base = np.where(
        has_solar,
        ASSUMPTIONS["daily_kwh_home_with_solar"],
        ASSUMPTIONS["daily_kwh_home_without_solar"],
    )
    sigma_home = 0.35
    daily_kwh = base * rng.lognormal(-0.5 * sigma_home**2, sigma_home, n_homes)

    weekend = index.dayofweek.to_numpy() >= 5
    hour = index.hour.to_numpy()
    shape = np.where(weekend, WEEKEND_SHAPE[hour], WEEKDAY_SHAPE[hour])
    sigma_hour = 0.25
    noise = rng.lognormal(-0.5 * sigma_hour**2, sigma_hour, (len(index), n_homes))
    demand = shape[:, None] * daily_kwh[None, :] * noise

    day_number = (index.normalize() - index.normalize()[0]).days.to_numpy()
    n_days = day_number.max() + 1
    for home in np.flatnonzero(has_ev):
        start = rng.integers(18, 22, n_days)[day_number]
        charging = (hour >= start) & (hour < start + ASSUMPTIONS["ev_charge_hours"])
        demand[:, home] += charging * ASSUMPTIONS["ev_charger_kw"]
    return demand


def export_profile(folder) -> None:
    """Write the average-day profile and its assumptions as files (pipeline task S4)."""
    import json
    from pathlib import Path

    folder = Path(folder)
    solar, plain = ASSUMPTIONS["daily_kwh_home_with_solar"], ASSUMPTIONS["daily_kwh_home_without_solar"]
    table = pd.DataFrame(
        {
            "hour": np.arange(24),
            "weekday_share_of_day": WEEKDAY_SHAPE.round(5),
            "weekend_share_of_day": WEEKEND_SHAPE.round(5),
            "weekday_kw_home_with_solar": (WEEKDAY_SHAPE * solar).round(3),
            "weekday_kw_home_without_solar": (WEEKDAY_SHAPE * plain).round(3),
            "is_simulated": True,
        }
    )
    table.to_csv(folder / "demand_profile_simulated.csv", index=False)
    meta = {"is_simulated": True, "is_measured": False, "made_by": "grid-sim/gridsim/demand.py"}
    (folder / "demand_profile_simulated.meta.json").write_text(json.dumps(meta | ASSUMPTIONS, indent=2))


if __name__ == "__main__":
    from pathlib import Path

    export_profile(Path(__file__).resolve().parents[1])
