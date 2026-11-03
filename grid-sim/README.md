# Grid simulation

Owner: Mithil Rajapakse (electrical engineering).

## Purpose

Estimate how each home's exports change the voltage on the neighbourhood line, and whether the transformer is heading for an overload. The scheduler uses that estimate so the houses share the transformer's capacity instead of all exporting at midday.

## Planned contents

- A pandapower model of a low-voltage neighbourhood
- The 50-home case used as a success check (overload hours avoided)
- A single call the scheduler can make: planned exports in, voltage and loading out
- Notes for the February tabletop grid, which will show an overload being avoided

Not implemented yet.
