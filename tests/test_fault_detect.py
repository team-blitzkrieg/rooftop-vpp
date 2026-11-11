"""Fault-detection tests. Made-up readings only."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fault-detect"))

from faultdetect import check_settings, flag_underperformance, load_reference, peer_ratio  # noqa: E402
from faultdetect.settings_check import NOT_READ, OK, TOO_LOOSE, TRIPS_EARLY, summary  # noqa: E402

RATED_KW = 5.0


def compliant() -> dict:
    return {key: spec["value"] for key, spec in load_reference()["settings"].items()}


def sunny_days(n_days: int) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=24 * n_days, freq="h")
    bell = np.clip(np.sin((index.hour - 6) / 12 * np.pi), 0, None) * 4.0
    return pd.DataFrame({"expected_kw": bell, "actual_kw": bell * 0.97}, index=index)


def test_compliant_settings_pass():
    findings = check_settings(compliant())
    assert all(f.result == OK for f in findings)
    assert summary(findings) == "Settings OK"


def test_pre_blackout_settings_are_flagged_as_tripping_early():
    old = compliant() | {"uv1_pu": 0.85, "uv1_s": 2.0, "uf_hz": 49.0, "of_hz": 51.0, "lvrt_enabled": False}
    results = {f.key: f.result for f in check_settings(old)}
    for key in ("uv1_pu", "uv1_s", "uf_hz", "of_hz", "lvrt_enabled"):
        assert results[key] == TRIPS_EARLY
    assert results["ov1_pu"] == OK
    assert summary(check_settings(old)) == "Settings need review"


def test_loose_settings_and_unread_settings_need_review():
    loose = compliant() | {"ten_min_ov_pu": 1.10, "reconnect_delay_s": 60}
    del loose["ov2_pu"]
    results = {f.key: f.result for f in check_settings(loose)}
    assert results["ten_min_ov_pu"] == TOO_LOOSE
    assert results["reconnect_delay_s"] == TOO_LOOSE
    assert results["ov2_pu"] == NOT_READ


def test_normal_days_raise_no_alert():
    days = flag_underperformance(sunny_days(10), RATED_KW)
    assert days["judged"].all()
    assert not days["alert"].any()


def test_seeded_fault_is_flagged_on_the_third_day():
    frame = sunny_days(10)
    frame.loc["2025-01-05":, "actual_kw"] *= 0.4  # most of a string lost on 5 Jan
    days = flag_underperformance(frame, RATED_KW)
    alerts = [str(day) for day in days.index[days["alert"]]]
    assert alerts[0] == "2025-01-07"
    assert not days.loc[: pd.Timestamp("2025-01-04").date(), "alert"].any()


def test_one_bad_day_is_not_an_alert():
    frame = sunny_days(10)
    frame.loc["2025-01-05", "actual_kw"] *= 0.3
    assert not flag_underperformance(frame, RATED_KW)["alert"].any()


def test_cloudy_days_are_not_judged():
    frame = sunny_days(5)
    frame["expected_kw"] *= 0.3
    frame["actual_kw"] = 0.0
    days = flag_underperformance(frame, RATED_KW)
    assert not days["alert"].any()


def test_peer_ratio_spots_the_weak_home():
    days = pd.date_range("2025-01-01", periods=5)
    table = pd.DataFrame({f"home{i}": 4.0 for i in range(5)}, index=days)
    table["home2"] = 2.0
    ratio = peer_ratio(table)
    assert np.allclose(ratio["home2"], 0.5)
    assert np.allclose(ratio["home0"], 1.0)
