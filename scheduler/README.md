# Scheduler

Owner: Senesh Fernando (software). Mithil Rajapakse checks the tariff figures and the grid limits before they are encoded.

## Purpose

Every few minutes, choose what happens to the next unit of solar power:

- use it in the house now
- store it for the 6:30–10:30 pm peak
- shift EV charging or water heating into sunny hours
- hold exports back when the local transformer is near its limit

The choice uses the forecast, the published CEB tariff, and the limit returned by the grid simulation.

## Planned contents

- A tariff table kept as data, so a CEB rate change is an edit to a file rather than a code change
- One decision step with a written input and output
- A daily schedule for the home
- A savings report against the inverter's default settings

Not implemented yet.
