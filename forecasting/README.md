# Forecasting

Owner: Senesh Fernando (software).

## Purpose

Predict, for the next few hours, how much the roof will generate and how much the household will use. The scheduler cannot decide without both numbers.

## Planned contents

- Features built from Open-Meteo and NASA POWER weather, plus recent readings from the Edge Unit
- LightGBM models for solar output and for household demand
- A small evaluation step so we can quote a forecast error
- A plain table of predictions for the scheduler to read

Training files do not live in this folder. See `data/`. Nothing here runs yet.
