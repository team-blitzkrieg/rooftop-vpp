# Scope decision

Owner: Mithil Rajapakse (decides with Tatiana, Senesh and mentor Dr Umanga Pilapitiya).
Written: 11 Nov 2026.
**Status: Option C chosen by Mithil on 11 Nov 2026. Team and mentor confirm by Fri 20 Nov 2026** after the first two interviews.

## The question

What does the system do in a real home during the pilot, and what only happens on the lab rig?

The proposal says the Edge Unit decides every few minutes and "holds back export" and moves loads. The app mock-ups say the pilot is read-only and never controls devices. The concept paper cannot say both. This file picks one.

## What changed in the market (this affects the choice)

Details and sources are in `ui-ux-changes.md` (top section). Check each point against the primary documents before it goes in the paper.

1. Since 11 Sep 2026 new homes can only join **Net Plus**.
2. Under Net Plus, all solar is exported and paid at a fixed rate. The home pays the normal slab rate for everything it uses. Moving appliances into sunny hours does not change the bill.
3. A battery changes this: solar-plus-storage is reported at LKR 45.53 per kWh in the prioritized period vs LKR 15.81 at other times.
4. The feed-in rates are reported as valid to 24 Feb 2027, so they may change during the pilot. The change itself is being appealed.
5. PUCSL says fewer than half of installed capacity has the new protection settings, and the utility has no real-time view of rooftop solar.

## What each kind of home gains from timing (and from watching)

| Home type | Does moving appliance use into sunny hours save money? | What else helps |
|---|---|---|
| Existing Net Metering | No. Exports bank 1-for-1. | Catching faults. Settings check. |
| Existing Net Accounting | Yes, probably. Using solar avoids a buy price far above the export rate. Check the numbers with a bill. | Faults, settings check. |
| New Net Plus | No. | Catching faults (every lost unit is lost income). Settings check. If a battery is added: dispatch timing. |
| Every home | | Time-of-use tariff shifting, where the home has a TOU meter. |
| The utility | | Seeing rooftop output, voltage and compliance. |

**What this tells us:** the strongest value that holds in every case is **protecting solar income and the grid** (watching, fault and settings detection, utility visibility). Load shifting helps only some homes.

## The options

| | A: Full control in homes | B: Monitor only | C: Monitor + Protect + Advise in homes. Control on the lab rig only |
|---|---|---|---|
| What homes get | Edge Unit changes inverter, battery, EV settings | Dashboard and alerts only | Dashboard, alerts, settings check, a daily suggestion where it has value. Homeowner acts. |
| What the lab rig shows | Same | Nothing | A tabletop low-voltage grid where the software prevents an overload by limiting or storing |
| Risk | High: safety, warranty, utility approval, regulator | Low | Low to medium |
| Approvals needed | Utility, installer, regulator, warranty owners. Very likely not possible by February. | Homeowner consent, utility awareness | Same as B |
| Matches the proposal's "AI that decides"? | Yes | No | Yes, on the rig. Honest about homes. |
| Evidence we can produce by 31 Dec | Not possible (no homes yet) | Forecast and fault results | Forecast, fault, 50-home simulation, rig plan |
| Fit with 3 students in 50 days | Poor | Good | Good |

## Recommendation: Option C

**Monitor, protect and advise in homes (read-only). Show control on the tabletop rig only.**

Reasons:
1. **Safety and warranty.** Writing to a home inverter needs permission from the owner, installer, manufacturer and utility. We will not have that for 2-5 homes by February.
2. **Evidence.** The 50-home simulation can show control working, which is what the proposal's success measure (transformer overload hours avoided) needs.
3. **Value holds under every scheme.** Fault and settings detection helps Net Metering, Net Accounting and Net Plus homes.
4. **It matches a named public problem.** The regulator reports the missing protection settings and the lack of real-time visibility.
5. **It is honest.** The paper says exactly what the homes did and what the rig did.

## What changes if we choose C

1. **Rewrite the lead message** of the concept paper from "shifts load to save bills" to "makes rooftop solar visible, safe and income-protecting, and shows the control that becomes possible".
2. Pillar order in the paper: (1) fault and settings detection, (2) voltage and transformer prediction in the 50-home simulation, (3) forecast and scheduling.
3. The headline numbers (365 GWh a year moved, USD 65-75 million) assumed evening battery use. Under Net Plus they only hold if homes add batteries. Recheck them. Flag them as estimates.
4. App text: "Advice" mode on every pilot home, "Bench" mode only on the rig (`ui-ux-changes.md` item 12).
5. Edge Unit: Tier 1 and Tier 2 for homes, Tier 3 for the lab only (`edge-unit-plan-for-tatiana.md`).

## Decision rule (so the vote is quick)

Choose **C** unless an interview gives a strong reason to switch:
- Switch to **B** if the utility or installers say even the read-only box needs approvals we cannot get before February.
- Switch to **A** only if the utility says in writing that it will approve third-party control for a pilot and the pilot owner agrees. Very unlikely. Do not plan for it.

## Decision record (fill in)

| Item | Value |
|---|---|
| Date decided | 11 Nov 2026 (Mithil). Tatiana, Senesh and mentor still to confirm by Fri 20 Nov. |
| Option chosen | C: Monitor + Protect + Advise in homes (read-only). Control on the lab rig only. |
| Who agreed | Mithil (11 Nov). Pending: Tatiana, Senesh, Dr Umanga Pilapitiya. |
| Reason in one sentence | It is safe, needs no approval to control home inverters, and its value (fault and settings detection, utility visibility) holds under every scheme. |
| What would make us revisit | An interview showing even a read-only box needs approvals we cannot get before February (switch to B), or written utility approval for third-party control (consider A). |

## Open facts that could change the answer

1. Which scheme is the pilot home on? (Mithil, 14 Nov)
2. Does the pilot home have a battery? (Mithil, 14 Nov)
3. Is the Net Plus-only rule still in force when the paper is written? (Mithil, check on 18 Nov and 18 Dec)
4. Is the "prioritized" period for stored-solar payments the evening peak? (Read the PUCSL document and ask in interviews.)
