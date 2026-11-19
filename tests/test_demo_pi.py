"""The demo Pi generator. No network."""

from datetime import datetime, timedelta

from edge.sim.demo_pi import (
    DEMAND_SCALE_KW,
    MAX_BATCH,
    SYSTEM_KW,
    TIMEZONE,
    batches,
    generate_readings,
    iter_slots,
    latest_slots,
    run,
    seed_for,
)


def _day(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 21, hour, minute, tzinfo=TIMEZONE)


def test_seed_is_the_date_plus_the_slot():
    slot = _day(10, 15)
    assert seed_for(slot, 15) == seed_for(slot, 15)
    assert seed_for(slot, 15) != seed_for(slot + timedelta(minutes=15), 15)
    assert seed_for(slot, 15) != seed_for(slot + timedelta(days=1), 15)


def test_readings_are_non_negative_and_labelled():
    slots = iter_slots(_day(0, 0), _day(23, 45), 15)
    readings = generate_readings(slots, 15)
    assert readings
    for row in readings:
        assert row["pv_kw"] >= 0
        assert row["consumption_kw"] >= 0
        assert row["import_kw"] >= 0
        assert row["export_kw"] >= 0
        assert row["pv_kw"] <= SYSTEM_KW
        assert row["data_label"] == "SIMULATED"
        assert row["is_simulated"] is True
        net = row["consumption_kw"] - row["pv_kw"]
        assert row["import_kw"] == round(max(net, 0.0), 4)
        assert row["export_kw"] == round(max(-net, 0.0), 4)


def test_same_slots_repeat_exactly():
    slots = latest_slots(_day(12, 7), 15)
    assert generate_readings(slots, 15) == generate_readings(slots, 15)


def test_batches_stay_within_48():
    slots = iter_slots(_day(0, 0) - timedelta(days=2), _day(23, 45), 15)
    readings = generate_readings(slots, 15)
    assert len(readings) > MAX_BATCH
    chunks = batches(readings)
    assert chunks
    assert all(1 <= len(chunk) <= MAX_BATCH for chunk in chunks)
    assert [row for chunk in chunks for row in chunk] == readings


def test_night_is_dark_and_the_peaks_are_morning_and_evening():
    night = generate_readings([_day(3, 0)], 15)[0]
    noon = generate_readings([_day(12, 0)], 15)[0]
    morning = generate_readings([_day(7, 0)], 15)[0]
    evening = generate_readings([_day(19, 30)], 15)[0]
    assert night["pv_kw"] == 0
    assert noon["pv_kw"] > 0
    assert morning["consumption_kw"] > night["consumption_kw"]
    assert evening["consumption_kw"] > night["consumption_kw"]
    assert evening["consumption_kw"] > DEMAND_SCALE_KW * 0.5


def test_dry_run_and_missing_key_do_not_post(capsys, monkeypatch):
    monkeypatch.delenv("DEMO_DEVICE_KEY", raising=False)

    def refuse(url, key, readings):
        raise AssertionError("posted")

    code = run(["--dry-run"], now=_day(12, 0), poster=refuse, pause_s=0)
    assert code == 0
    assert "nothing posted" in capsys.readouterr().out

    code = run(["--backfill-days", "0"], now=_day(12, 0), poster=refuse, pause_s=0)
    assert code == 0
    assert "DEMO_DEVICE_KEY is not set" in capsys.readouterr().out


def test_a_post_prints_counts_and_not_the_key(capsys, monkeypatch):
    monkeypatch.setenv("DEMO_DEVICE_KEY", "super-secret-token")
    seen = {}

    def poster(url, key, readings):
        seen["key"] = key
        seen["count"] = len(readings)
        return 200, len(readings)

    code = run(["--resolution", "hourly"], now=_day(12, 0), poster=poster, pause_s=0)
    out = capsys.readouterr().out
    assert code == 0
    assert seen["key"] == "super-secret-token"
    assert seen["count"] <= MAX_BATCH
    assert "status 200" in out
    assert "super-secret-token" not in out


def test_backfill_days_are_capped():
    code = run(["--backfill-days", "40", "--dry-run"], now=_day(12, 0), pause_s=0)
    assert code == 2
