# Fault detection

Owner: Mithil Rajapakse (electrical engineering).

## Purpose

Catch inverter faults and unsafe settings from the readings the Edge Unit already collects, and raise an alert the dashboard can show. Version 0 has two rules. It reads only. It never changes an inverter.

## What is here

| File | What it is |
|---|---|
| `ceb_inverter_settings.json` | The CEB recommended inverter settings (voltage, frequency, ride-through, reconnection) as data. Source: CEB, "Recommended Settings for Inverters", GM meeting of 25 Feb 2025. Pipeline task R5. |
| `faultdetect/settings_check.py` | Rule (b). Compares settings read from an inverter with the CEB table. |
| `faultdetect/underperformance.py` | Rule (a). Flags output far below what the weather says it should be. Also a neighbour comparison. |
| `evaluate.py` | Tests rule (a) on faults inserted by hand into a year of simulated output |
| `results/seeded_fault_test.csv` | The output of `evaluate.py` |
| `../tests/test_fault_detect.py` | 8 unit tests |

Run:

```bash
python -m pytest tests/test_fault_detect.py
```

```bash
python fault-detect/evaluate.py
```

## Rule (b): settings check

The CEB table for plants under 1 MW:

| Setting | CEB value |
|---|---|
| 10-minute average voltage limit | 1.06 of nominal (243.8 V). Disconnect within 3 s. |
| Over-voltage stage 1 / stage 2 | 1.15 for 2 s / 1.20 for 0.16 s |
| Under-voltage stage 1 / stage 2 | 0.70 for 10 s / 0.45 for 0.32 s |
| Frequency | Stay connected from 47 to 52 Hz. Outside that, clear in 0.2 s. |
| Low-voltage ride-through | Must be active |
| Reconnect | Voltage 0.94 to 1.06, frequency 49.5 to 50.5 Hz, wait at least 600 s, ramp up over 900 s |

Each setting gets one of five results:

| Result | Meaning |
|---|---|
| `ok` | Matches the CEB value within 1% |
| `trips_too_early` | The inverter would leave the grid during a dip in voltage or frequency. This is the problem behind the February 2025 blackout. |
| `too_loose` | The inverter stays on, or reconnects, when it should not |
| `different` | Differs from an exact CEB value |
| `not_read` | The Edge Unit could not read it. This also needs review. |

The homeowner sees one line: "Settings OK" or "Settings need review".

Not done yet: reading these settings from a real inverter. Each brand stores them in different registers. That is Edge Unit work, after the pilot inverter is known.

## Rule (a): under-performance

1. Look only at sunny hours: hours when the expected output is at least half the system size.
2. A day is judged only if it has 3 or more sunny hours.
3. A judged day is "low" when actual energy is under 60% of expected energy.
4. Alert when 3 judged days in a row are low.

The rule waits 3 days because weather data is often wrong for one day.

### Test on seeded faults (simulated data)

Five sites, the year 2025, a 5 kW system. "Expected" comes from Open-Meteo archive weather. "Healthy actual" comes from NASA POWER weather, an independent source, so the two disagree the way a weather service and a real roof would. The fault starts on 1 June.

| Case | Sites that raised an alert | Days to the first alert |
|---|---|---|
| Healthy all year | 2 of 5 sites raised false alerts: 3 false alert days in 5 site-years (about 1,400 judged days) | |
| Inverter off | 5 of 5 | 3 |
| Half the panels out | 5 of 5 | 3 |
| Export stuck at 40% of system size | 3 of 5 | 18 to 79 |
| 15% loss from dirt | 3 of 5, but only after 51 to 112 days | Treat as not detected |

What this says:
- Large faults are caught in 3 days at every site.
- A stuck export limit and slow losses are **not** caught reliably. They need a different rule (clipping detection, a long-term trend).
- The false alarm rate is low but not zero.

### Limits

- **No measured inverter data was used.** Both series come from the same pvlib model with different weather. Real roofs have shading, dirt and odd orientations that this test does not include. The thresholds must be re-tuned on pilot data.
- The neighbour comparison (`peer_ratio`) has unit tests only. It cannot be tested properly until several real homes report.
- No fault labels were invented from real logs, because there are no real logs yet.

## Next steps

1. Agree the list of checks with an installer and the utility contact (ask in the interviews, see `docs/interview-script.md`).
2. Add a clipping rule for a stuck export limit.
3. Re-run `evaluate.py` on pilot inverter data when it arrives.
