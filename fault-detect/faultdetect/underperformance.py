"""Rule (a): output far below what the weather says it should be.

Two versions:

* ``flag_underperformance`` compares one home with the output expected from
  weather data. It only judges sunny hours and it waits for the problem to
  repeat, because weather data is often wrong for a single day.
* ``peer_ratio`` compares one home with the other homes nearby. It needs no
  weather data, so a wrong forecast cannot trigger it.
"""

from __future__ import annotations

import pandas as pd

SUNNY_SHARE = 0.5  # an hour counts as sunny when expected output >= 50% of rated
MIN_SUNNY_HOURS = 3  # a day is judged only if it has this many sunny hours
LOW_RATIO = 0.6  # a judged day is "low" when actual / expected is below this
REPEAT_DAYS = 3  # alert when this many judged days in a row are low


def daily_ratio(
    frame: pd.DataFrame,
    rated_kw: float,
    sunny_share: float = SUNNY_SHARE,
    min_sunny_hours: int = MIN_SUNNY_HOURS,
) -> pd.DataFrame:
    """Per day: sunny hours, actual and expected energy in them, and the ratio.

    ``frame`` needs a datetime index and columns ``actual_kw`` and ``expected_kw``.
    Days with too few sunny hours get ``judged = False`` and are never flagged.
    """
    sunny = frame[frame["expected_kw"] >= sunny_share * rated_kw]
    days = sunny.groupby(sunny.index.date).agg(
        sunny_hours=("expected_kw", "size"),
        actual_kwh=("actual_kw", "sum"),
        expected_kwh=("expected_kw", "sum"),
    )
    days["ratio"] = days["actual_kwh"] / days["expected_kwh"]
    days["judged"] = days["sunny_hours"] >= min_sunny_hours
    return days


def flag_underperformance(
    frame: pd.DataFrame,
    rated_kw: float,
    low_ratio: float = LOW_RATIO,
    repeat_days: int = REPEAT_DAYS,
    **kwargs,
) -> pd.DataFrame:
    """Add ``low`` and ``alert`` columns to the daily table.

    ``alert`` is True on a judged day when it and the judged days before it
    make ``repeat_days`` low days in a row. Days that are not judged are
    skipped, not counted as healthy.
    """
    days = daily_ratio(frame, rated_kw, **kwargs)
    days["low"] = days["judged"] & (days["ratio"] < low_ratio)
    days["alert"] = False
    run = 0
    for day, row in days.iterrows():
        if not row["judged"]:
            continue
        run = run + 1 if row["low"] else 0
        days.loc[day, "alert"] = run >= repeat_days
    return days


def peer_ratio(daily_kwh_per_kw: pd.DataFrame, min_peers: int = 3) -> pd.DataFrame:
    """Each home's daily yield divided by the median of the other homes.

    ``daily_kwh_per_kw`` has one row per day and one column per home, in kWh
    per kW of system size. A value near 1.0 is normal. Returns NaN where fewer
    than ``min_peers`` other homes reported.
    """
    out = pd.DataFrame(index=daily_kwh_per_kw.index, columns=daily_kwh_per_kw.columns, dtype=float)
    for home in daily_kwh_per_kw.columns:
        others = daily_kwh_per_kw.drop(columns=home)
        median = others.median(axis=1).where(others.notna().sum(axis=1) >= min_peers)
        out[home] = daily_kwh_per_kw[home] / median.where(median > 0)
    return out
