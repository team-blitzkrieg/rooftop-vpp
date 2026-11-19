"""Seeded stand-in for Mithil's Pi on site demo-sim.

Every reading is labelled SIMULATED. The seed is the Colombo date plus the
slot, so a rerun writes the same numbers and the ingest upsert replaces the
same hour. This process only POSTs readings. It never sends a setpoint.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pvlib.location import Location

SITE_ID = "demo-sim"
LATITUDE = 6.90
LONGITUDE = 79.86
SYSTEM_KW = 3.0
DEMAND_SCALE_KW = 1.2
TIMEZONE = ZoneInfo("Asia/Colombo")
DEFAULT_INGEST_URL = "https://rooftop-web-gamma.vercel.app/api/ingest"
MAX_BATCH = 48
MAX_BACKFILL_DAYS = 14
DEFAULT_RESOLUTION = "15min"
LOOKBACK_MINUTES = 180
RESOLUTIONS = {"15min": 15, "hourly": 60}


def seed_for(moment: datetime, minutes: int) -> int:
    """Fixed seed from the local date and the slot index inside that day."""
    local = moment.astimezone(TIMEZONE)
    slot = local.hour * (60 // minutes) + local.minute // minutes
    return local.year * 1_000_000 + local.month * 10_000 + local.day * 100 + slot


def floor_slot(moment: datetime, minutes: int) -> datetime:
    local = moment.astimezone(TIMEZONE).replace(second=0, microsecond=0)
    return local.replace(minute=(local.minute // minutes) * minutes)


def iter_slots(start: datetime, end: datetime, minutes: int) -> list[datetime]:
    cursor = floor_slot(start, minutes)
    last = floor_slot(end, minutes)
    slots: list[datetime] = []
    while cursor <= last:
        slots.append(cursor)
        cursor += timedelta(minutes=minutes)
    return slots


def latest_slots(now: datetime, minutes: int, lookback_minutes: int = LOOKBACK_MINUTES) -> list[datetime]:
    """Closed slots in the recent window, including the current slot."""
    end = floor_slot(now, minutes)
    start = end - timedelta(minutes=max(lookback_minutes - minutes, 0))
    return iter_slots(start, end, minutes)


def backfill_slots(now: datetime, days: int, minutes: int) -> list[datetime]:
    local = now.astimezone(TIMEZONE)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    return iter_slots(start, local, minutes)


def select_slots(now: datetime, minutes: int, backfill_days: int) -> list[datetime]:
    if backfill_days < 0:
        raise ValueError("backfill_days cannot be negative")
    if backfill_days == 0:
        return latest_slots(now, minutes)
    return backfill_slots(now, backfill_days, minutes)


def _cloud_factor(seed: int) -> float:
    rng = np.random.default_rng(seed)
    return float(rng.uniform(0.35, 1.0))


def _load_noise(seed: int) -> float:
    rng = np.random.default_rng(seed + 17)
    return float(rng.normal(0.0, 0.02 * DEMAND_SCALE_KW))


def _load_kw(hour: float, seed: int) -> float:
    morning = math.exp(-0.5 * ((hour - 7.0) / 1.1) ** 2) * 0.55
    evening = math.exp(-0.5 * ((hour - 19.5) / 1.3) ** 2) * 0.95
    shape = 0.22 + morning + evening
    return round(max(0.0, DEMAND_SCALE_KW * shape + _load_noise(seed)), 4)


def generate_readings(slots: list[datetime], minutes: int) -> list[dict]:
    """One labelled reading per slot. Powers are kW and never negative."""
    if not slots:
        return []
    index = pd.DatetimeIndex(pd.to_datetime(slots))
    if index.tz is None:
        index = index.tz_localize(TIMEZONE)
    location = Location(LATITUDE, LONGITUDE, tz="Asia/Colombo", altitude=10.0)
    clear = location.get_clearsky(index, model="ineichen")
    ghi = clear["ghi"].to_numpy(dtype=float)
    readings: list[dict] = []
    for moment, irradiance in zip(slots, ghi, strict=True):
        local = moment.astimezone(TIMEZONE)
        seed = seed_for(local, minutes)
        hour = local.hour + local.minute / 60.0
        raw = 0.0 if not math.isfinite(float(irradiance)) else float(irradiance) / 1000.0 * SYSTEM_KW * _cloud_factor(seed)
        pv = round(min(SYSTEM_KW, max(0.0, raw)), 4)
        load = _load_kw(hour, seed)
        net = load - pv
        readings.append(
            {
                "timestamp": local.isoformat(timespec="seconds"),
                "pv_kw": pv,
                "consumption_kw": load,
                "import_kw": round(max(net, 0.0), 4),
                "export_kw": round(max(-net, 0.0), 4),
                "data_label": "SIMULATED",
                "is_simulated": True,
            }
        )
    return readings


def batches(readings: list[dict], size: int = MAX_BATCH) -> list[list[dict]]:
    if size < 1 or size > MAX_BATCH:
        raise ValueError(f"batch size must be 1 to {MAX_BATCH}")
    return [readings[index : index + size] for index in range(0, len(readings), size)]


def post_batch(url: str, key: str, readings: list[dict]) -> tuple[int, int | None]:
    """POST one batch. The key stays in the header and is not returned."""
    request = urllib.request.Request(
        url,
        data=json.dumps({"readings": readings}).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Device-Key": key,
            "User-Agent": "rooftop-demo-pi",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read()
    upserted = None
    try:
        payload = json.loads(raw.decode())
        if isinstance(payload, dict) and isinstance(payload.get("upserted"), int):
            upserted = payload["upserted"]
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        upserted = None
    return status, upserted


def run(
    argv: list[str] | None = None,
    *,
    now: datetime | None = None,
    poster=post_batch,
    pause_s: float = 1.0,
) -> int:
    parser = argparse.ArgumentParser(description="Post seeded SIMULATED readings for demo-sim. Does not command a device.")
    parser.add_argument("--backfill-days", type=int, default=0)
    parser.add_argument("--resolution", choices=tuple(RESOLUTIONS), default=DEFAULT_RESOLUTION)
    parser.add_argument("--dry-run", action="store_true", help="Print counts and do not POST")
    args = parser.parse_args(argv)
    if args.backfill_days < 0 or args.backfill_days > MAX_BACKFILL_DAYS:
        print(f"backfill_days must be from 0 to {MAX_BACKFILL_DAYS}.")
        return 2
    minutes = RESOLUTIONS[args.resolution]
    slots = select_slots(now or datetime.now(TIMEZONE), minutes, args.backfill_days)
    readings = generate_readings(slots, minutes)
    chunks = batches(readings)
    print(f"site {SITE_ID} slots {len(readings)} batches {len(chunks)} resolution {args.resolution}")
    if args.dry_run:
        print("dry run: nothing posted")
        return 0
    key = os.environ.get("DEMO_DEVICE_KEY", "").strip()
    if not key:
        print("DEMO_DEVICE_KEY is not set. Skipping the demo Pi. Nothing was posted.")
        return 0
    url = os.environ.get("INGEST_URL", "").strip() or DEFAULT_INGEST_URL
    for index, chunk in enumerate(chunks, start=1):
        status, upserted = poster(url, key, chunk)
        shown = upserted if upserted is not None else "-"
        print(f"batch {index}/{len(chunks)} readings {len(chunk)} status {status} upserted {shown}")
        if status != 200:
            return 1
        if pause_s and index < len(chunks):
            time.sleep(pause_s)
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
