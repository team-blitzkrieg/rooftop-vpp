# Parked for later

Written: 11 Nov 2026. These are real tasks, saved so they are not lost. Do not start them yet unless `project-pipeline.md` says so.

---

## 1. The prediction model (Mithil wants to contribute)

Status: not started. Planned in the pipeline as tasks S2, S3, S5 (Senesh leads, Mithil contributes). Details here are for when you pick it up.

### What we predict

| Prediction | Why | Who uses it |
|---|---|---|
| Solar output for tomorrow (per hour or per 15 minutes) | Plan the day. Compare with actual output to spot faults. | Scheduler, fault detection, app forecast screen |
| Home electricity use | Plan loads and battery use | Scheduler |
| Voltage and transformer loading on the feeder | Share limited grid capacity fairly | Grid simulation, utility dashboard |

### Plain-English plan

1. **Baseline first.** Predict tomorrow's solar as "same as yesterday at this hour", then as "clear-sky maximum scaled by cloud cover". Score both. Any model we build must beat these. If it does not, say so.
2. **Then the real model.** LightGBM (a tree-based model that suits table data) using weather features: cloud cover, sunshine, temperature, hour of day, day of year, and the forecast from the day before.
3. **Give a range, not one number.** The app shows an "8 in 10 days fall in this band" shaded area. Train the model to give a low, middle and high estimate (quantile prediction). Then check that about 80% of real values fall inside the band. Do not print the "8 in 10" claim until this check passes.
4. **Split by date, never at random.** Train on early months, test on later months. Random splits leak the future and give fake good scores.
5. **Score with:** MAE (average error in kW), RMSE (punishes big misses), nMAE (error as a share of system size, so homes of different sizes can be compared), and band coverage (the 80% check).

### Where Mithil can contribute (pick any)

- Define the success numbers and the test periods (S2). This is an engineering judgement, not coding.
- The voltage model: connect the forecast to the pandapower feeder so that predicted solar gives predicted voltage rise at each house.
- The clear-sky "expected output" curve that the fault detector uses (`pvlib` is already in `requirements.txt`).
- Read the results critically. Ask: does it work on cloudy days? On the days the grid was stressed?

### Known gaps (be honest in the paper)

- **No real Sri Lankan rooftop generation data in the repository.** The data README says the PV series are simulated model output, not meter readings. Real pilot data arrives in February 2027 at the earliest (unless task S6 captures some earlier).
- Because of that, a forecast score on simulated PV measures weather-forecast quality, not real-roof quality. Say this in the paper.
- Weather sources in the repo: Open-Meteo (archive, historical forecast, previous-day forecast) and NASA POWER. Use the "previous-day forecast" data to train, because that is what we would really have the morning before.

### First three tasks when you start

1. Open `data/README.md`. Read which columns are weather inputs and which are simulated PV.
2. Write the baseline in a notebook. Score it on June 2024 vs a later month, once you have more than one month. (The sample folder has only June 2024; the raw folders have more.)
3. Report the baseline score in the Friday check-in.

---

## 2. Other parked items

| Item | When | Owner | Note |
|---|---|---|---|
| Build the Edge Unit hardware | After Tatiana's step 4 (parts approved), and the pilot inverter is known | Tatiana | See `edge-unit-plan-for-tatiana.md` |
| Tabletop low-voltage grid rig | January 2027 | Tatiana + Mithil | Needs university sign-off on mains-side work |
| Live utility dashboard (working, not mock-up) | Early Feb 2027 | Senesh | After mock-ups are tested with the utility |
| Sinhala and Tamil | Before pilot | Senesh | Needs translation help |
| Data protection review of consent and retention | Before recruiting homes | Mithil | Ask university or mentor who can review |
| Cheaper production board (ESP32-class) | After pilot | Tatiana | Only if pilot proves the need |
| Battery dispatch for Net Plus homes with storage | After pilot | Senesh + Mithil | Depends on the prioritized-period rule |
| Installer grading or certification idea (PUCSL names the gap) | After paper | Mithil | Could be a later add-on |
