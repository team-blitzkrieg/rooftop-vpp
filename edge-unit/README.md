# Edge Unit

Owner: Tatiana Armstrong (mechatronics) and Mithil Rajapakse (electrical engineering).

## Purpose

The box in the house. A Raspberry Pi reads the solar inverter, the battery and the EV charger over RS485/Modbus, and writes back the action the scheduler has chosen: use, store, shift or hold.

## Planned contents

- A Modbus client, and a short register map for each device we actually have on the pilot
- A separate adapter for the inverter, the battery and the EV charger, so a second brand does not force a rewrite of the scheduler
- A loop that reads measurements every few minutes and applies the latest command
- Local configuration for the pilot home: serial port, device address, model
- Wiring notes for the Pi and the RS485 adaptor

No device code has been written yet.
