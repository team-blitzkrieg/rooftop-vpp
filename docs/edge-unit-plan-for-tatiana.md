# Edge Unit: parts and to-do list for Tatiana

Owner: Tatiana Armstrong (mechatronics), with Mithil Rajapakse (electrical).
Written: 11 Nov 2026.

**Status: planning only. Nothing is built or ordered yet.** Do not start building until Mithil confirms the scope (`scope-decision.md`, due 20 Nov) and the pilot home's inverter is known.

Prices below are **rough estimates in US dollars**. They are not quotes. Get local quotes before ordering. Assume about LKR 300 per USD for a first guess and check today's rate.

---

## 1. What the box must do

1. Read the solar inverter every minute (power, voltage, energy, status). Read-only at pilot homes.
2. Read grid import and export, if the inverter does not provide it.
3. Store readings if the internet drops. Keep up to 7 days. Upload when it comes back (the apps promise this).
4. Send readings to our server over the internet, securely.
5. Report its own health: last seen, queue size, retries, clock drift, signal strength, firmware version (the technician app shows all of these).
6. Be installable by a technician in under 30 minutes.
7. Cost little enough that a household, an installer, or the utility will pay for it.

Not needed in pilot homes: switching or limiting the inverter. That stays on the lab rig only.

---

## 2. Design idea: three tiers, one software

Build one software stack. Sell or install it in three tiers. Every home gets Tier 1. Add parts only when a home needs them.

| Tier | Adds | Who gets it | Rough parts cost |
|---|---|---|---|
| **1: Monitor** | Reads the inverter only | Every pilot home | US$ 65-90 |
| **2: Monitor + Meter** | Adds an energy meter for grid import/export and home use | Homes where the inverter cannot report grid flow, or Net Plus homes that want a second reading | + US$ 25-45 |
| **3: Control (lab only for now)** | Adds relays or a protocol link to a battery or EV charger | Lab rig only. Not for pilot homes. | + US$ 30-80 (lab) |

Why tiers: most homes only need Tier 1. Keeping Tier 2 and 3 optional keeps the base price low and keeps electrical work (which needs a licensed electrician) out of most installs.

---

## 3. Parts list (Tier 1 and Tier 2)

### Tier 1: Monitor

| Part | Choice | Est. cost | Why |
|---|---|---|---|
| Computer | **Raspberry Pi 4 Model B, 1 GB** | about US$ 35 | Runs Python, so it shares code with the scheduler. Has Ethernet (more reliable than home Wi-Fi). The 1 GB model's price was held at US$ 35 when Raspberry Pi raised prices on 2 GB and larger models in early 2026 because of memory costs. Prices move, so recheck. |
| Cheaper alternative | Raspberry Pi Zero 2 W | about US$ 15-20 | Use if cost matters more than Ethernet. Wi-Fi only. Check stock locally. |
| Memory card | High-endurance microSD, 32 GB | US$ 8-12 | Ordinary cards wear out from constant writing. Use this type and the write-saving settings in section 5. |
| Power supply | Good 5 V / 3 A supply with a firm plug | US$ 6-10 | Weak supplies are the top cause of random reboots. Do not use phone chargers. |
| Inverter link | **Isolated USB-to-RS485 adapter** | US$ 10-15 | RS485 is the wired link most inverters have. "Isolated" protects the Pi from voltage spikes. |
| Clock | DS3231 real-time clock module | US$ 2-3 | Keeps correct time with no internet. The technician app requires clock drift under 2 s. |
| Enclosure | Plastic box, IP54, with cable glands | US$ 6-10 | Protects from dust and splashes. |
| Small parts | RS485 120-ohm termination resistor, surge protection diodes on the A/B lines, terminal block, short cables, labels with a QR code | US$ 5-8 | Needed for a stable wired link and for the commissioning QR step in the app. |
| **Tier 1 total** | | **about US$ 70-95** (about 65 with the Zero 2 W) | |

### Tier 2 additions

| Part | Choice | Est. cost | Why |
|---|---|---|---|
| Energy meter | Single-phase DIN-rail Modbus meter, for example the Eastron SDM120 or SDM230 class | US$ 25-40 | Reads real grid import/export, voltage and frequency. Works with any inverter brand. |
| Split-core CT clamp (if the chosen meter uses one) | 60-100 A clamp | US$ 5-10 | Clamp-on, so no cutting of wires. |

**Safety rule:** meters and CT clamps in the main board must be fitted by a licensed electrician. The Edge Unit itself plugs into a normal socket and touches only the RS485 data cable and the network. Nobody on the team opens the inverter or touches DC wiring.

### Tier 3 (lab rig only)

| Part | Use | Est. cost |
|---|---|---|
| Relay board or smart contactor | Switch a test load or heater | US$ 10-25 |
| Modbus or OCPP link to a battery or EV charger | Study control on the bench | depends on kit |
| Inverter simulator or a donated used inverter | Test commands safely | borrow if possible |

---

## 4. What can the box talk to? (check each in the manuals)

Start with the inverter at the pilot home. Then add brands from `inverter-landscape-sri-lanka.md`.

| Inverter family | Likely way to read it | Watch out for |
|---|---|---|
| Huawei SUN2000 | Modbus TCP via the Smart Dongle (network), or RS485 | Installer must enable Modbus. Reports of dongle instability. |
| Growatt | RS485 Modbus RTU | Register map differs by model. |
| Solax | RS485 or LAN Modbus | Differs by model. |
| Sungrow | Modbus TCP via WiNet dongle | |
| SMA, Fronius | Modbus TCP (SunSpec) | Usually easy. |
| Unknown or cheap brand | Use the **energy meter (Tier 2)** only | Do not guess register addresses. Never write to an unknown device. |

Network vs wire: if the inverter has a network dongle, reading over the home network needs no wiring at the inverter. It also needs no technician at the inverter. Try this first. Use RS485 when there is no dongle.

---

## 5. Build for many homes, not one (the scalable part)

Rules for the software and hardware design. Tatiana owns these. Each rule has a test.

| # | Rule | How we know it works |
|---|---|---|
| 1 | **One register map file per inverter model** (a plain YAML file: name, address, scale, unit, source tag). Adding a brand means adding a file, not code. | A new inverter is added in under 1 day with no code change to the reader. |
| 2 | **Same output format for every brand.** Use a fixed list of fields: solar kW, AC kW, grid kW, voltage, frequency, energy today, status. Where possible, use SunSpec field names. | The scheduler and dashboard never mention a brand name. |
| 3 | **Read-only by default.** Writing to the inverter is switched off in the software on every pilot unit. Turning it on needs a lab-only setting. | Test: on a pilot image, a write command is refused and logged. |
| 4 | **Never write to an unknown device.** | Test with a fake unknown device. |
| 5 | **Store and forward.** Save readings to disk. Upload in batches. Re-sending the same batch twice must not make duplicates. | Unplug the router for 6 hours. After reconnect, no gaps, no duplicates. |
| 6 | **Versioned message format.** Every message carries a schema version. | The server accepts old and new versions at the same time. |
| 7 | **Secure by default.** Each unit has its own ID and its own key. Outgoing connection only. No open ports on the home network. | Port scan of the unit shows nothing open. |
| 8 | **Updates over the air, with rollback.** If an update fails to start, the unit goes back to the last good version. | Test with a deliberately broken update. |
| 9 | **Watchdog and safe card.** Hardware watchdog restarts a stuck unit. Logs live in memory and are flushed on a schedule, so the card lasts. | 7-day power-cut test. Card still healthy. |
| 10 | **Health report every minute.** Same fields the technician app shows. | Server can show "last seen" for every unit. |
| 11 | **Simulator first.** Write a fake inverter (a small Modbus server in Python) so everyone can test without hardware. | Team can run the full chain on a laptop. |
| 12 | **Provisioning by QR code.** Scanning the label registers the unit to a site. No typing of keys. | A technician registers a unit in under 2 minutes. |

Grow plan:
- 5 homes: a Raspberry Pi per home, simple server.
- 50 homes: a device registry, a dashboard of unit health, automatic alerts.
- 500+ homes: swap the Pi for a cheaper board built around a low-cost chip (for example ESP32-S3 with an isolated RS485 chip). Same message format, same server. Estimated target cost at volume: **under US$ 40**. Only worth doing after the pilot proves what is needed.

---

## 6. Is the price fair for a household?

- A 3 kW home system costs about LKR 600,000-900,000 (calclk.com, 2026). A US$ 70-95 unit is about 2-4% of that.
- Under Net Plus, a 3 kW system earns about LKR 8,300 a month from feed-in (360 kWh x LKR 23.11). If the box catches a fault that cuts output by 10%, that is about LKR 830 a month protected. This is an example, not a promise.
- The utility gets value too (visibility of rooftop solar). The utility, the installer or a bulk buy could pay part of the cost. Ask this in the interviews (question 6).

Keep Tier 1 as the default offer. Do not add parts to Tier 1 without a reason you can explain in one sentence.

---

## 7. Tatiana's to-do list

Do these in order. Planning and paper work first. **No building and no purchase until step 4 is signed off.**

| # | Task | Due | Done when |
|---|---|---|---|
| 1 | **Inventory check.** Walk the lab. List every part we already have (Pi boards, RS485 adapters, meters, relays, power supplies, enclosures, any inverter or battery). Fill the table in section 8. | Fri 13 Nov | Table filled. Photo of the parts. Mithil has seen it. |
| 2 | **Get the pilot home's inverter facts** with Mithil: make, model, firmware, size, whether it has a Wi-Fi/LAN dongle, an RS485 port, a meter, a battery. | Sat 14 Nov | One page with photos of the inverter label and ports. |
| 3 | **Download manuals and the Modbus register document** for the pilot inverter and the next two likely brands. Put links (not files with private data) in `edge-unit/README.md`. | Fri 27 Nov | For each brand: register list located, and a note on "how do we read it" (network or RS485). |
| 4 | **Approve the parts list.** Use the inventory and section 3. Mark each part: have / buy / skip. Mithil signs off the budget. | Fri 20 Nov | Signed list with local price quotes from at least 2 shops. |
| 5 | **Order parts** (only after step 4). Ask suppliers for the delivery time. | Fri 27 Nov | Order placed. Arrival date known. Target: parts in hand by 11 Dec. |
| 6 | **Write the inverter simulator** (fake Modbus inverter in Python) and the register-map file format. Share it with Senesh. | Fri 4 Dec | Reader runs against the simulator on a laptop. |
| 7 | **First real read.** With the Pi (or a laptop and the adapter), read one register from the pilot inverter. Read-only. Log it. | Fri 11 Dec (only if permission and parts are ready) | One real value matches the inverter display. |
| 8 | **Bench test list** for store-and-forward, power cut, and update rollback (section 5 rules 5, 8, 9). | Fri 18 Dec | Test results in a table, pass or fail. |
| 9 | **Wiring and install notes** for a technician (RS485 pins, termination, grounding at one end only, QR label). One page with photos. | Fri 18 Dec | A technician who has not seen the unit can follow it. |

If a due date slips by more than 3 days, tell Mithil the same day so the plan can be changed.

---

## 8. Inventory table (Tatiana fills this in)

| Part | Have it? (Y/N, how many) | Where it is | Tier it is useful for | Notes |
|---|---|---|---|---|
| Raspberry Pi (which model?) | | | 1 | |
| microSD cards (size, type) | | | 1 | |
| 5 V power supplies | | | 1 | |
| USB-to-RS485 adapters (isolated?) | | | 1 | |
| RS485 HAT for the Pi | | | 1 | |
| DS3231 RTC modules | | | 1 | |
| Enclosures, cable glands | | | 1 | |
| Modbus energy meters | | | 2 | |
| CT clamps | | | 2 | |
| Relay boards | | | 3 (lab) | |
| Test inverter or simulator | | | 3 (lab) | |
| Battery or EV charger for the bench | | | 3 (lab) | |
| Multimeter, crimp tools, labels | | | all | |

Use what the lab already owns before buying. Match the choice in section 3 to what is on this table.

---

## 9. Questions only Tatiana can answer

1. Does Curtin Colombo's lab have an inverter or simulator we can use for the bench demo (the technician app calls it BENCH-EX-01)? If not, can we borrow one?
2. How long do local suppliers take to deliver a Pi, a meter and an isolated RS485 adapter?
3. Who at the university can approve mains-side work in the lab and sign off the tabletop rig as safe?
