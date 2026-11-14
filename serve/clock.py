"""Asia/Colombo timestamps."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from forecasting.config import TIMEZONE

COL = ZoneInfo(TIMEZONE)


def parse_time(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize(COL)
    else:
        stamp = stamp.tz_convert(COL)
    return stamp


def floor_hour(moment: datetime | None = None) -> pd.Timestamp:
    if moment is None:
        moment = datetime.now(COL)
    stamp = pd.Timestamp(moment)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize(COL)
    else:
        stamp = stamp.tz_convert(COL)
    return stamp.floor("h")


def to_py(value) -> datetime:
    stamp = parse_time(value)
    return stamp.to_pydatetime()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
