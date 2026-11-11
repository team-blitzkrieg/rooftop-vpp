# Project pipeline: what, when, who, and what "done" means

Written: 11 Nov 2026 (Wednesday). Next deadline: **concept paper, Thu 31 Dec 2026** (50 days).
Later milestone: pilot and demo in February 2027.

People:
- **Mithil** = Mithil Rajapakse, team lead, electrical engineering. Owns interviews, grid simulation, fault detection, the paper.
- **Tatiana** = Tatiana Armstrong, mechatronics. Owns the Edge Unit.
- **Senesh** = Senesh Fernando, software. Owns data, forecasting, scheduler, dashboard, app screens.
- **Mentor** = Dr Umanga Pilapitiya.

Related files in this folder:
`scope-decision.md` | `facts-check.md` | `challenge-rules.md` | `paper-outline.md` | `ui-ux-changes.md` | `edge-unit-plan-for-tatiana.md` | `interview-script.md` | `inverter-landscape-sri-lanka.md` | `parked-for-later.md`

---

## Pipeline chart

Open **[pipeline-chart.html](pipeline-chart.html)** in a browser. It shows every task by date and by owner, with major blockers in red and the gates as dashed lines. Keep the colours in that file up to date when a task changes status (the `tasks` list near the bottom of the file).

---

## The big picture in one table

| Stage | Dates | Goal in plain words | Gate at the end |
|---|---|---|---|
| 0. Decide | 11-20 Nov | Agree what we are building and what facts we need | Gate 0 on Fri 20 Nov |
| 1. Learn | 11 Nov - 4 Dec | Talk to the utility and installers. Learn the real rules and the real inverters. | Gate 1 on Fri 27 Nov |
| 2. Data and baselines | 16 Nov - 6 Dec | Make sure the data works. Get a first simple forecast score. | Gate 2 on Sun 6 Dec |
| 3. Build the evidence | 30 Nov - 20 Dec | Produce the results that go in the paper | Gate 3 on Tue 15 Dec (first results) |
| 4. Write | 14 - 31 Dec | Write, check, review, submit | Gate 4 on Tue 22 Dec (full draft), Gate 5 on Tue 29 Dec (submit) |
| 5. Pilot prep | Jan - Feb 2027 | Recruit homes, build the rig, run the pilot | after the paper |

Each gate has **criteria**. If the criteria are not met, do not move on. Fix the gap or cut something from the "if behind" list (bottom of this file).

---

## Weekly rhythm

| When | What | Time |
|---|---|---|
| Monday | Team check-in: what is done, what is next, what is blocked | 15 min |
| Friday | Show what works (demo or file). Update this file's status column. | 30 min |
| Any day | If a task slips more than 3 days, tell Mithil the same day | |

Status words: **TODO**, **DOING**, **DONE**, **BLOCKED** (say why).

---

## Stage 0: Decide (11-20 Nov)

| ID | Task | Owner | Due | Done when | Status |
|---|---|---|---|---|---|
| D1 | Decide the scope using `scope-decision.md` | Mithil + all, mentor informed | Fri 20 Nov | Decision record in `scope-decision.md` is filled in, and Tatiana, Senesh and the mentor have confirmed | DOING (Option C chosen by Mithil 11 Nov. Waiting for team and mentor to confirm by Fri 20 Nov.) |
| D2 | Pilot home fact sheet: scheme, inverter make/model/firmware, size, battery, dongle, RS485 port, meter, photos of the label | Mithil with Tatiana | Sat 14 Nov | Sheet below is filled in | TODO |
| D3 | Book 4 interviews (2 utility-side if possible, 2 installers). Send the message from `interview-script.md`. | Mithil | Fri 13 Nov | Dates in the calendar | TODO |
| D4 | Check the challenge rules: paper length, format, judging criteria, how to submit, any deadline for an intent form | Mithil | Fri 13 Nov | One page of rules saved in `docs/` | DONE 11 Nov: `challenge-rules.md`. Format, weighting and how to submit are not published yet. Send message 4. |
| D5 | Verify the Net Plus rule and feed-in rates in primary sources (PUCSL annex, Ministry letter of 11 Sep 2026, CEB or LECO notices) | Mithil | Wed 18 Nov | A note saying which statements are confirmed and which are not | DONE 11 Nov: `facts-check.md`. Two statements are wrong (home battery rate, evening window). Re-check 18 Nov and 18 Dec. |
| D6 | Fix the app mock-ups P0 list in `ui-ux-changes.md` (items 1-12) | Senesh | Fri 4 Dec (start now) | All P0 boxes ticked and screens re-exported | TODO |

**Pilot home fact sheet (fill in; no names or addresses)**

| Item | Answer |
|---|---|
| Scheme (Net Metering / Accounting / Net Plus) and agreement end date | |
| System size (kW) and panel count | |
| Inverter make, model, firmware | |
| Phases (1 or 3) | |
| Battery? make and size | |
| Wi-Fi/LAN dongle? RS485 port free? | |
| Existing meter or CT on site? | |
| Does the owner allow read-only data capture? | |
| Does the owner allow an Edge Unit install in Feb? | |
| Is a smart/TOU meter fitted? | |

**Gate 0 (Fri 20 Nov): "We agree what we are building."**
Criteria:
1. Scope decision recorded (D1).
2. Pilot home facts known (D2).
3. At least 2 interviews are booked and at least 1 is done.
4. Paper rules known (D4).
5. Rate and rule facts checked (D5).
Sign-off: Mithil, with the other two agreeing in the Friday meeting.

---

## Stage 1: Learn (11 Nov - 4 Dec)

| ID | Task | Owner | Due | Done when | Status |
|---|---|---|---|---|---|
| R1 | Do at least 3 interviews (1 utility, 2 installers), 4 is better. Use `interview-script.md`. | Mithil (lead). Others take notes. | Fri 27 Nov | 3+ note sheets saved in `docs/interviews/`, no personal data | TODO |
| R2 | Ask the utility and SLSEA for anonymised counts of inverter make and size | Mithil | Send by Mon 16 Nov | Request sent. Reply, or a note that it was refused. | TODO |
| R3 | Fill the numbers into `inverter-landscape-sri-lanka.md` | Mithil | Fri 4 Dec | At least 1 measured number or a small survey with n >= 3 | TODO |
| R4 | Tariff table as data (domestic slab rates, time-of-use windows, feed-in bands with valid-to dates, battery rate and its prioritized period) | Senesh drafts. Mithil verifies the numbers. | Draft Wed 18 Nov. Verified Fri 20 Nov. | `scheduler/tariffs.yaml` (or similar) exists. Every number has a source line and date. | TODO |
| R5 | Find the CEB recommended inverter settings (voltage, frequency, ride-through) and turn them into a table the fault-detect code can use | Mithil | Fri 27 Nov | Table saved in `fault-detect/` with source | DONE 11 Nov: `fault-detect/ceb_inverter_settings.json`. Check each number against the CEB PDF. |
| R6 | Edge unit research tasks: inventory, parts list, manuals (see Tatiana's list) | Tatiana | Fri 13 Nov (inventory), Fri 27 Nov (manuals) | `edge-unit-plan-for-tatiana.md` steps 1-4 done | TODO |
| R7 | Find the source for "2,542 MW" in the proposal. Decide which national number the paper uses. | Mithil | Fri 20 Nov | One agreed number with source | DONE 11 Nov: 2,542 MW is the National System Operator figure for Sep 2026 (Newswire, 26 Sep 2026). See `facts-check.md`. |

**Gate 1 (Fri 27 Nov): "We know the real situation."**
Criteria:
1. 3 or more interviews filed (at least 1 from the utility side).
2. We know what approval a 2-5 home pilot needs and who signs it.
3. The tariff table is verified.
4. The inverter brands for the pilot are chosen (pilot home plus the top two brands from interviews).
5. The CEB settings table exists.
If criteria 1 or 2 fail: stop building new things. Spend the next 2 days booking the missing interviews.

---

## Stage 2: Data and baselines (16 Nov - 6 Dec)

| ID | Task | Owner | Due | Done when | Status |
|---|---|---|---|---|---|
| S1 | Set up Python on Windows (install pytest) and run the existing tests | Senesh | Mon 16 Nov | `python -m pytest` runs and passes (or failures are listed) | TODO |
| S2 | Write down the forecast plan: which target, which time resolution, how the test set is chosen (split by date, never random), which scores (see `parked-for-later.md`) | Senesh + Mithil | Fri 20 Nov | One page agreed | TODO |
| S3 | Simple baseline forecast (yesterday-same-hour, then clear-sky) and its score | Senesh | Fri 27 Nov | Score table saved | TODO |
| S4 | Demand data plan. There is no real household data yet. Use a clearly labelled synthetic profile for Sri Lankan homes (morning and 6:30-10:30 pm peaks), with the source and assumptions written down. | Mithil + Senesh | Fri 4 Dec | Profile file with a "Simulated" label and assumptions | DONE 11 Nov (first version): `grid-sim/demand_profile_simulated.csv`. Senesh to review. |
| S5 | First version of the improved forecast (see `parked-for-later.md`) | Senesh, with Mithil | Sun 6 Dec | Beats the baseline on the test set, or we report that it does not | TODO |
| S6 | If the pilot owner agrees, start saving the inverter's own app history for 2-4 weeks (a manual export is fine). Real data matters more than anything simulated. | Tatiana + Mithil | Start by Mon 23 Nov | Data in `data/raw/` (not in git). A metadata note says how it was made. | TODO |

**Gate 2 (Sun 6 Dec): "Baselines work."**
Criteria:
1. Tests run.
2. A baseline forecast has a score on a held-out period.
3. A synthetic demand profile exists and is labelled.
4. Edge Unit parts are approved and ordered (Tatiana's steps 4-5).
5. App P0 fixes at least 80% done.

---

## Stage 3: Build the evidence (30 Nov - 20 Dec)

This stage produces the results the paper needs. The proposal's three success measures are: household bill reduction, transformer overload hours avoided in a 50-home simulation, and forecast error.

| ID | Task | Owner | Due | Done when | Status |
|---|---|---|---|---|---|
| B1 | **50-home simulation, baseline.** A pandapower model of one low-voltage feeder with a transformer, 50 homes, midday solar and an evening peak. Count transformer overload hours and over-voltage hours with no control. | Mithil | Sat 12 Dec | Script runs end to end. Results table saved. Assumptions listed (transformer size, cable, share of homes with solar). | DONE 11 Nov: `grid-sim/run.py`, `grid-sim/results/`. Feeder values are assumptions until the utility interview. |
| B2 | **Scheduler v0.** One decision step with written inputs and outputs. It reads the tariff table and picks use, store, shift or hold. It must depend on the home's scheme. | Senesh | Sat 12 Dec | Given a day of forecast and a tariff, it outputs a plan. At least 5 test cases pass (including a Net Plus home where it must say "no saving from timing"). | TODO |
| B3 | **Control result.** Run B1 again with the scheduler holding back export or storing. Compare overload hours with and without control. This is the main result. | Mithil + Senesh | Fri 18 Dec | A table and one chart: overload hours with and without. | DOING. First result 11 Nov with a stand-in export limit (`grid-sim/README.md`). Re-run with Senesh's scheduler (B2). |
| B4 | **Fault and settings detection v0.** Two rules: (a) output far below the clear-sky expectation while nearby weather is clear, (b) inverter voltage and frequency settings outside the CEB table. Test on seeded faults. | Mithil | Tue 15 Dec | It flags a fault inserted by hand in a test file, and does not flag a normal day. Count of false alarms reported. | DONE 11 Nov: `fault-detect/`. Simulated data only. Re-tune on pilot data. |
| B5 | **Edge Unit simulator and first read** (see Tatiana's steps 6-7) | Tatiana | Simulator Fri 4 Dec. First real read Fri 11 Dec. | Reader runs against the simulator. One real value matches the inverter display, if allowed. | TODO |
| B6 | **Savings and income report** by scheme, using the same tariff table | Senesh | Fri 11 Dec | Report for one test home per scheme. Numbers can be re-computed by hand. | TODO |
| B7 | **Utility dashboard screens** (4 screens, see `ui-ux-changes.md` item 13). Real numbers from B1 where possible. | Senesh | Fri 11 Dec | 4 screens exported | TODO |
| B8 | **Rest of the app fixes (P1)** | Senesh | Fri 18 Dec | P1 items 13-24 done or logged as later | TODO |
| B9 | **App test with real people** (3 homeowners, 2 installers) | Senesh + Mithil | Fri 18 Dec | Notes with the top 5 confusions | TODO |

**Gate 3 (Tue 15 Dec): "First results exist."**
Criteria:
1. B1 baseline results exist (overload hours with no control).
2. B2 scheduler produces a plan for each scheme in the test cases.
3. B4 flags the seeded fault.
4. The paper outline is agreed (W1).
5. Edge Unit simulator runs.
If B1 is missing, nothing else matters for the paper. Everyone helps B1.

---

## Stage 4: Write (14 - 31 Dec)

Suggested paper skeleton (check against the challenge rules from D4):

1. Problem and evidence (national numbers with sources; the Feb 2025 blackout; hosting limits; settings compliance under 50%).
2. What changed: Net Plus and what it means for value.
3. Our solution: Edge Unit, three tiers, read-only in homes, control on the rig.
4. AI methods: forecast, voltage/transformer model, fault and settings detection.
5. Results: forecast score, 50-home overload hours with and without control, fault detection test.
6. What we learned from interviews.
7. Feasibility, cost (Edge Unit parts), safety and approvals, privacy.
8. Pilot plan for Feb 2027 and what we will measure.
9. Limits and risks, stated plainly.
10. Sources.

| ID | Task | Owner | Due | Done when | Status |
|---|---|---|---|---|---|
| W1 | Paper outline with a one-line note per section | Mithil | Tue 15 Dec | Outline saved. Each section has an owner. | DOING. Draft 11 Nov: `paper-outline.md`. Team to agree by Tue 15 Dec. |
| W2 | Draft sections 1, 2, 6, 7, 9 | Mithil | Fri 18 Dec | Draft text saved | TODO |
| W3 | Draft sections 4 and 5 (forecast, simulation, fault) | Senesh + Mithil | Fri 18 Dec | Draft text with tables | TODO |
| W4 | Draft section 3 (Edge Unit design, cost, safety) | Tatiana | Fri 18 Dec | Draft text with a block diagram and the tier table | TODO |
| W5 | Figures: architecture diagram, app screens, overload chart, forecast chart | Senesh (screens, charts), Tatiana (hardware diagram), Mithil (architecture) | Sun 20 Dec | Each figure saved with its source file | TODO |
| W6 | Number check: every number in the paper has a source or a file that produced it | Mithil | Mon 21 Dec | A table: number, where it comes from | TODO |
| W7 | **Full draft to the mentor** | Mithil | Tue 22 Dec | Mentor has it. Review dates agreed. | TODO |
| W8 | Fix mentor comments | All | Sun 27 Dec | Comment list cleared | TODO |
| W9 | Read-aloud pass for plain language. Format check against the rules. | All | Mon 28 Dec | Passes the format checklist | TODO |
| W10 | **Submit** (a day or two early) | Mithil | Tue 29 Dec | Confirmation saved | TODO |

**Gate 4 (Tue 22 Dec): "Full draft exists."**
Criteria: every section has text, all results are in, all figures are placed, the number check (W6) is done, the mentor has it.

**Gate 5 (Tue 29 Dec): "Submitted."**
Criteria: submission confirmation saved. 31 Dec is the buffer, not the plan.

---

## Stage 5: Pilot prep (Jan - Feb 2027) (rough plan, detail later)

| Task | Owner | Target |
|---|---|---|
| Recruit 2-5 homes in Colombo and Gampaha. Consent forms. Pilot approval path from the interviews. | Mithil | Early Jan |
| Build and test Edge Units (Tier 1, some Tier 2). Bench tests from Tatiana's list. | Tatiana | Mid Jan |
| Build the tabletop low-voltage grid for the control demo (Tier 3, lab only) | Tatiana + Mithil | End Jan |
| Move the app from mock-up to a working prototype | Senesh | Jan |
| Live utility dashboard | Senesh | Early Feb |
| Pilot and demonstration | All | Feb |

---

## Risks

| Risk | How likely | What we do |
|---|---|---|
| Interviews slip | Medium | Book 4 so that 3 happen. Start Monday. If no utility interview by 27 Nov, ask the mentor to introduce someone. |
| Rules change again (the Net Plus rule is being appealed) | Medium | Keep the tariff and scheme as data files. Re-check on 18 Nov and 18 Dec. State the date of every rule in the paper. |
| No real inverter data before the deadline | High | Say so in the paper. Use simulated data labelled as simulated. Capture whatever real data we can (S6). |
| Parts arrive late | Medium | Build the simulator first. Order by 27 Nov. |
| Pilot home does not allow install | Low to medium | The paper only needs a plan for Feb. Have a second home candidate. |
| Team time (exams, other classes) | Medium | Agree this week who has real hours each week. If hours are short, use the cut list. |
| Two different national numbers in circulation (2,090 MW vs 2,542 MW) | Already happening | Task R7. |

---

## Cut list: if we fall behind, drop in this order

1. Real Edge Unit read (B5 second half). Keep the simulator and the design text.
2. P2 app items and the user tests (B9). Keep P0 and the utility screens.
3. Second improved forecast (S5). Keep the baseline score.
4. Demand data realism (S4). Keep the labelled synthetic profile.

**Never cut:** the scope decision, the interviews, the 50-home simulation (B1, B3), the number check (W6), the submission.

---

## Status log (add one line per Friday)

| Date | What is done | What is blocked | Next week |
|---|---|---|---|
| Wed 11 Nov | Docs written: scope, UI changes, edge plan, interview script, inverter facts, this pipeline, messages. D1: Option C chosen by Mithil. | D1 needs Tatiana, Senesh and mentor to confirm | Book interviews, fact sheet, Tatiana's inventory |
| Wed 11 Nov (later) | D4, D5, R5, R7, S4, B1, B4 done. B3 first result. W1 and Mithil's paper sections drafted. 13 new tests pass. Nothing committed to git yet. | Nothing sent yet: messages 1-7 still wait for Mithil. Paper format not published. | Send messages 1-4. Fix the home battery claim everywhere (`facts-check.md`). |
