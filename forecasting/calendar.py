"""Sri Lanka public holidays for 2024.

The dates are the public holidays named in the order under the Holidays Act,
No. 29 of 1971, published in Gazette Extraordinary No. 2341/46 on 20 July 2023.
Poya days are in that list. A date outside 2024 is not flagged. This is not a
later year's gazette.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from forecasting.config import TIMEZONE

# date -> short name, as the gazette words it (Independence Day keeps their spelling).
HOLIDAYS_2024: dict[date, str] = {
    date(2024, 1, 15): "Tamil Thai Pongal Day",
    date(2024, 1, 25): "Duruthu Full Moon Poya Day",
    date(2024, 2, 4): "Independence Day",
    date(2024, 2, 23): "Navam Full Moon Poya Day",
    date(2024, 3, 8): "Maha Sivarathri Day",
    date(2024, 3, 24): "Medin Full Moon Poya Day",
    date(2024, 3, 29): "Good Friday",
    date(2024, 4, 11): "Id-Ul-Fitr",
    date(2024, 4, 12): "Day prior to Sinhala and Tamil New Year",
    date(2024, 4, 13): "Sinhala and Tamil New Year Day",
    date(2024, 4, 23): "Bak Full Moon Poya Day",
    date(2024, 5, 1): "May Day",
    date(2024, 5, 23): "Vesak Full Moon Poya Day",
    date(2024, 5, 24): "Day following Vesak Full Moon Poya Day",
    date(2024, 6, 17): "Id-Ul-Allah (Hadji Festival Day)",
    date(2024, 6, 21): "Poson Full Moon Poya Day",
    date(2024, 7, 20): "Esala Full Moon Poya Day",
    date(2024, 8, 19): "Nikini Full Moon Poya Day",
    date(2024, 9, 16): "Milad-Un-Nabi",
    date(2024, 9, 17): "Binara Full Moon Poya Day",
    date(2024, 10, 17): "Vap Full Moon Poya Day",
    date(2024, 10, 31): "Deepavali Festival Day",
    date(2024, 11, 15): "Il Full Moon Poya Day",
    date(2024, 12, 14): "Unduvap Full Moon Poya Day",
    date(2024, 12, 25): "Christmas Day",
}


def is_holiday(day: date) -> bool:
    return day in HOLIDAYS_2024


def holiday_flag(timestamps: pd.Series) -> pd.Series:
    """1.0 on a 2024 public holiday in Asia/Colombo, else 0.0."""
    local = pd.to_datetime(timestamps)
    if local.dt.tz is None:
        local = local.dt.tz_localize(TIMEZONE)
    else:
        local = local.dt.tz_convert(TIMEZONE)
    return local.dt.date.map(lambda day: 1.0 if day in HOLIDAYS_2024 else 0.0).astype(float)
