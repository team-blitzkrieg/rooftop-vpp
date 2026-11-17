# UI/UX changes needed

Owner: Senesh Fernando (builds the fixes). Mithil Rajapakse reviews.
Written: 11 Nov 2026.
Source: review of `household-screens-light.html` (25 screens) and `technician-screens-light.html` (17 screens). Both files sit in `E:\AIconomy\`. Screen numbers below match the numbers on the artboards. H = household app. T = technician app.

## How to use this file

1. Do every P0 item first. Do not show the screens to a homeowner, installer or the utility until P0 is done.
2. Then P1. Then P2.
3. Tick the box when the change is made and the artboard is re-exported.

Priority meaning:
- P0 = wrong or misleading. Fix before anyone sees it.
- P1 = important gap. Fix before the concept paper is submitted (31 Dec 2026).
- P2 = polish. Fix before the February 2027 pilot.

---

## Why many changes are needed: the rules changed

New facts found on 11 Nov 2026 (check them against the primary sources, see `scope-decision.md`):

- Since 11 Sep 2026, new rooftop solar connections can only use **Net Plus**. Net Metering and Net Accounting are closed to new customers. Existing agreements keep their terms until they expire. The change is being appealed, so rules may move again.
- Under Net Plus, all solar is exported and paid at a fixed rate (LKR 23.11 per kWh for systems up to 10 kW). Every unit the home uses is paid for at the normal slab rate. **Running appliances when the sun shines does not change the bill.**
- Solar with a battery gets LKR 45.53 per kWh in the "prioritized" period for 15 years, and LKR 15.81 in other periods.
- The feed-in rates were reported as valid to 24 Feb 2027. They can change during the pilot.

What this does to the screens: the savings screen (H16) and the daily plan (H11) assume that using solar at home saves money. That is only true for some existing customers. The app must change its message by scheme.

---

## P0: fix first

| # | Screen | What is wrong | Change to make | Done when |
|---|---|---|---|---|
| 1 | H05, T03 | Scheme choices are Net Metering, Net Accounting, Net Plus, all equal. New homes can only have Net Plus. | Show Net Plus as the default for new sites. Keep the other two as "existing agreement". Add the agreement end date. Add a line: "Rules changed 11 Sep 2026". | A new site cannot pick a closed scheme. Existing sites can. |
| 2 | H16 | Claims LKR 1,060 saved on **net metering**. Under net metering, exported units bank 1-for-1, so moving use in time changes the bill by about zero. The table even shows banked credit falling 14 kWh and ignores it. | Rewrite by scheme. **Net Metering:** show kWh only. No LKR saving. **Net Accounting:** show LKR saving, count the lost export income. **Net Plus:** show income earned (generated kWh x rate) and "income at risk from faults". Do not claim savings from shifting. | Each scheme has its own version of the screen. A reviewer can recompute every number by hand. |
| 3 | H11, H12, H13 | The daily plan assumes "run appliances in the solar window" saves money. Not true under Net Plus. | Make the plan depend on the scheme. Net Plus: plan around cheap time-of-use periods only, or hide the plan and show "No saving from timing under your scheme". Net Accounting: keep the solar-window plan. Show one line explaining why the plan looks as it does. | The "Best time to run appliances" card never appears on a scheme where it has no value. |
| 4 | H11 | Washing machine (11:00-12:00) and EV charger (11:00-14:00) overlap. Together they use 4.2 kW plus the home base load. Both say "covered by solar". Solar at 11:00 is about 3.6 kW. | The plan must add all loads together before it says "covered". Show a combined line chart. Move or shorten the EV charge if the sum is above solar. | Total planned load never exceeds forecast solar plus allowed grid import. |
| 5 | H17, H07 | "Edge unit offline for 48 min" is **Active**, but the unit reconnected at 12:36. | Mark it Resolved. Show an alert as Active only while the cause is still present. | Alert state matches the heartbeat data. |
| 6 | H06 vs H10 | Same day: "Generated 14.2 kWh" on Home, "So far 8.7 kWh" on Forecast. | Use one number source. Both screens read the same value at the same time. | Same value on both screens. |
| 7 | H11, H15 vs most screens | Times jump between 11:32 and 15:40 on the same day. | Pick one "now" for the whole mock set. Use it everywhere. | All "now" times agree. |
| 8 | H04, H21b, H16 | The same user agrees to join at 15:42 on 10 Nov, leaves at 16:05, and has 10 days of savings history. | Use a user who joined earlier. Make the withdraw flow a separate persona. | Dates tell one consistent story. |
| 9 | T03 vs T10 | SITE-021 shows "Not commissioned" at 15:40 but its commissioning receipt is dated 15:34. | Make the receipt come after the "Not commissioned" screens in the story, or change the clock times. | The order of events makes sense. |
| 10 | H21 vs H03 | Withdraw says "Keep anonymised pilot totals (as consented)". The consent screen never asked for that. | Add a consent line for anonymised totals on H03 and H04. Or remove it from H21. | Consent, receipt and withdrawal wording match. |
| 11 | All | The mock user is named "Senesh" and uses his real name in the withdrawal text. | Use a made-up name. | No real team member name in any mock. |
| 12 | Proposal vs both apps | The proposal says the edge unit writes commands and holds back export. The apps say "never controls devices". | Add a clear "Mode" label on the app: **Advice** (all pilot homes) or **Bench** (lab only). Decide the scope first (`scope-decision.md`), then make the words match the decision. | The app, the proposal and the concept paper say the same thing. |

---

## P1: important gaps

| # | Where | Change |
|---|---|---|
| 13 | New: utility screens | There is no utility dashboard, and that is one of the three promised outputs. Add 4 screens: (a) feeder and transformer list with a risk colour, (b) one feeder: voltage and loading by hour, (c) fleet total: all homes as one plant, (d) compliance: which homes have the required inverter settings. |
| 14 | New: coordinator screens | The technician app mentions a "pilot coordinator" but no coordinator screens exist. Add: sites overview, who is assigned, open cases, consent status. |
| 15 | New: inverter settings check (T, plus a status on H) | PUCSL reports that fewer than half of installed capacity has the updated protection settings (low-voltage ride-through) after the Feb 2025 blackout. Add a technician screen that reads the inverter's voltage and frequency protection settings and compares them with the CEB recommended settings. Show a simple "Settings OK / need review" status to the homeowner. This is a strong feature. It matches a problem the regulator named. |
| 16 | H17, H18 | Add "income lost today" in LKR to alerts (Net Plus homes). "Output 40% low = about LKR X lost today" is the message that makes a homeowner care. |
| 17 | H03, H20 | Check the consent and retention wording against Sri Lanka's data protection law. Ask the university or mentor who can review this. Keep the retention table: raw 90 days, hourly to the end of the pilot. |
| 18 | H05 / T04 | Tariff data must be editable data, not typed into the screen. Show the "rates valid to" date. Show a banner when the valid-to date is within 30 days. |
| 19 | T04 | Add an inverter brand picker. Top of the list: the brands in `inverter-landscape-sri-lanka.md`. For each brand show how data is read (RS485, or network via the brand's dongle). |
| 20 | T08 | "Doesn't match" must lead somewhere. Add a screen: pick which register is wrong, enter the correct value, save as a register-map review request. |
| 21 | H12 | The alternative window "Wed 11 Nov 11:30-12:30" is on the same day as the failed plan. Change it to another day or to a different load. Also check that the "8 in 10 days" claim for the forecast band matches the real forecast tests later. |
| 22 | H08 | Coverage says 82%, but 20 of 24 hours is 83%. Make the number match the text. Also state clearly whether the % is for yesterday or for 7 days. |
| 23 | H17 vs H08 and T13 | The data-gap alert is dated 7 Nov but the history shows the gap on 9 Nov. Make the dates match. |
| 24 | T15 | Bench mode: add limits on the command box (allowed range per command), a confirm step, and a visible "lab rig only" check. Free typing of `set_export_limit(` is risky. |

---

## P2: polish before the pilot

| # | Where | Change |
|---|---|---|
| 25 | All | Language: add Sinhala and Tamil. At minimum, plan the text so labels can be swapped. Leave room, because Sinhala and Tamil text is longer. |
| 26 | All | Contrast. The orange (#ff9800) and yellow (#ffa600) used as text on white probably fail the standard contrast check. Test with a contrast checker. Use a darker shade for text. Keep the bright shade for charts. |
| 27 | All | Touch targets at least 44 x 44 px. Check the small buttons, chips and icon buttons. |
| 28 | All | Never use colour alone. Status pills already have text. Check the charts. |
| 29 | H02, H01 | Add the missing screens: forgot password, request pilot credentials, pilot info sheet, help/contact, notification settings. |
| 30 | Both | Turn the static artboards into a clickable prototype (Figma). The HTML files are pictures. A prototype lets you test flows with real people. |
| 31 | H07, T12 | Offline text: say the unit keeps up to 7 days of data and will upload on reconnect. Check this against the final edge design (`edge-unit-plan-for-tatiana.md`). |
| 32 | T16 | Add a "Safety" reminder at the start of every site visit: work on the AC side and on the edge unit only. Never open the inverter or touch DC. |

---

## Test the screens with real people (after P0)

1. Show H06, H11, H16 to 3 homeowners. Ask them to explain in their own words what each number means. Write down where they get stuck.
2. Show T03-T10 to 2 installers. Ask them to walk through commissioning aloud. Time it. Target: under 20 minutes per site.
3. Show the utility screens (item 13) to the utility contact. Ask: "Would you open this every day? What is missing?"

Done when: at least 5 people have seen the screens and the top 5 confusions are listed and fixed or logged.

---

## Do not change

These parts are good. Keep them.
- Source tags: Measured, Estimated, Not available, Simulated. They build trust.
- Hatched gaps instead of zeros in history charts.
- Reason codes on failures (for example `PLAN_LOW_SOLAR`).
- Confirmation dialogs that name exactly what changes.
- Withdraw flow with a receipt.
- The offline banner and stale pill.
