# Fact check: scheme rule, feed-in rates and the national solar number

Owner: Mithil Rajapakse. Pipeline tasks D5 and R7. Checked: 11 Nov 2026. Re-check on 18 Nov and 18 Dec.

How the check was done: each primary document was fetched and read by software on 11 Nov 2026. **Open the PDF and read the quoted section yourself before a number goes in the paper.**

Status words: **Confirmed** (primary source says it), **Confirmed, secondary** (news reports agree, primary not found), **Wrong** (primary source says something else), **Not checked**.

## Primary sources used

| Short name | Document |
|---|---|
| PUCSL Decision | PUCSL, "Decision on Feed in Tariffs", Aug 2026 (24 pages). https://www.pucsl.gov.lk/wp-content/uploads/2026/08/Full-Final-Decision-on-Feed-in-Tariffs-August-2026.pdf |
| PUCSL Annex 2 | PUCSL, "Summary of Approved Feed in Tariffs - August 2026". https://www.pucsl.gov.lk/wp-content/uploads/2026/08/Annex-2-Summary-of-Approved-Feed-in-Tariffs.pdf |
| NSO statement | National System Operator, reported by Newswire, 26 Sep 2026. https://www.newswire.lk/2026/09/26/sri-lankas-solar-capacity-tops-3070-mw-as-grid-operator-outlines-new-measures/ |

The Ministry of Energy letter of 11 Sep 2026 was not found online. Ask for a copy in the utility interview.

## Two statements in our documents are wrong

### 1. Homes do NOT get the LKR 45.53 battery rate

| | |
|---|---|
| What we wrote | "Power stored in a battery and sold between 6:30 and 10:30 pm earns about LKR 45.5 per unit" (concept paper section 1, the proposal, the repo README, `scope-decision.md` point 3, `ui-ux-changes.md`) |
| What the primary source says | The solar-plus-battery tariff exists only for systems **above 250 kW**. 45.53 is for 250-1000 kW. Above 1000 kW it is 42.49. For up to 10 kW there is one rate, 23.11, at all hours. (PUCSL Annex 2, table 2) |
| Why | PUCSL Decision, section 3.2, gives three reasons: the system operator cannot see small batteries, large prosumers have the technical know-how, and batteries under 250 kW cost more because of import duty. It says tariffs for batteries below 250 kW "would be considered during the upcoming tariff reviews". |
| Status | **Wrong** for homes |

### 2. The prioritized window is 5:30 to 9:30 pm, not 6:30 to 10:30 pm

| | |
|---|---|
| What the primary source says | "Prioritized Feed in Time" is a 4-hour interval, set at **17:30 to 21:30** in this review. PUCSL can move the start by up to 3 hours either way. It is not fixed for the life of the agreement. (PUCSL Decision, section 3.2) |
| Where 6:30-10:30 pm came from | Probably the older CEB battery tariff reports (LKR 45.80, references [6] and [7] in `Solar-Proposal-Sources.md`). Not re-checked. |
| Status | **Wrong** |

### What these two change

1. A home battery earns nothing extra from evening export today. The household argument "store at midday, sell in the evening for LKR 45" must come out of the paper.
2. This makes Option C in `scope-decision.md` stronger: the value for homes is fault and settings detection and visibility. The table row "If a battery is added: dispatch timing" no longer holds for Net Plus homes.
3. PUCSL's first reason is our opening: the operator cannot see small batteries and small solar. A low-cost box that gives that visibility is what a future below-250 kW tariff needs. Say this in section 1 and section 6 of the paper.
4. The headline estimates (365 GWh a year moved to the evening, USD 65-75 million) assume home batteries discharging in the evening. No current tariff pays for that. Keep them only as a "what if PUCSL extends the battery tariff to homes" scenario, clearly labelled.
5. Parked item "Battery dispatch for Net Plus homes with storage" depends on a tariff that does not exist yet.

## Everything else

| # | Statement | Status | Source and note |
|---|---|---|---|
| 3 | Feed-in rates for new rooftop solar: 23.11 (up to 10 kW), 19.15 (10-40 kW), 17.11 (40-250 kW), 15.81 (above 250 kW), LKR per kWh | **Confirmed** | PUCSL Annex 2, table 2 |
| 4 | These rates took effect on 25 Aug 2026 | **Confirmed** | PUCSL Decision, section 1: effective "from August 25, 2026, until the next tariff revision" |
| 5 | The rates are valid to 24 Feb 2027 | **Confirmed, secondary** | pv magazine, 22 Sep 2026. The Decision text only says "until the next tariff revision". Write "reported as valid to 24 Feb 2027". |
| 6 | New rooftop connections can only join Net Plus. Net Metering and Net Accounting are closed to new connections and to extensions. | **Confirmed, secondary** | Sunday Times, 27 Sep 2026 (Ministry of Energy decision, systems connected after 11 Sep 2026). NSO statement: applications approved before 11 Sep 2026 go ahead unchanged, and new applications are accepted under Net Plus. The National Electricity Policy text quoted in the PUCSL Decision says all new agreements "shall be on 'net plus' basis". |
| 7 | The date is 11 Sep 2026 | **Confirmed, secondary. One source disagrees.** | Sunday Times and Newswire say 11 Sep 2026. pv magazine (22 Sep 2026) says systems connected "after March 5, 2026". Use 11 Sep 2026 and ask the utility which date applies to what. |
| 8 | New Net Plus agreements run for at most 12 years, and need a smart meter the utility can read remotely | **Confirmed, secondary** | pv magazine, 22 Sep 2026. Useful for us: it shows the utility wants remote data. |
| 9 | Existing Net Metering and Net Accounting agreements keep their terms | **Confirmed** | PUCSL Decision, Annex 3, 4(a): licensees "shall continue to facilitate Net Metering, Net Accounting and Net Plus schemes ... in accordance with the prosumer's selected scheme, under a two-meter arrangement" |
| 10 | Under Net Plus all generation is exported and paid at the feed-in rate, and the home pays the normal tariff for all it uses, so moving appliance use does not change the bill | **Consistent with the primary source** | The two-meter arrangement in Annex 3, 4(a). The exact wording of the Net Plus definition was not checked. Ask in the utility interview. |
| 11 | Battery schemes: exports are capped at 123 kWh per kW of contracted capacity in a 30-day billing cycle | **Confirmed** | PUCSL Annex 2, note 2. Only matters above 250 kW. |
| 12 | The rule change is being appealed | **Not checked** | No source found on 11 Nov. Do not state it in the paper without one. |
| 13 | "The utility is refusing new rooftop connections" (concept paper section 1) | **Too strong** | NSO statement: 2026 rooftop additions were exceeded, so distribution licensees "have been asked to closely monitor new rooftop solar approvals". The NSO calls it a temporary grid-security measure. Zero-export systems are not limited. Write "new approvals are restricted" instead. |

## R7: which national number the paper uses

Three numbers are in circulation. They have different dates and come from different bodies.

| Number | What it counts | Date | Source |
|---|---|---|---|
| **2,542 MW** rooftop (plus 534 MW ground-mounted, about 3,070 MW total) | Rooftop capacity connected under Net Metering, Net Accounting and Net Plus | Sep 2026 | National System Operator, reported by Newswire, 26 Sep 2026 |
| about 2,090 MW rooftop, 129,302 connections | Rooftop capacity and connections | End Sep 2025 | PUCSL, "Analysis on Rooftop Solar Integration and Industry Growth", Dec 2025 |
| 1,935 MW rooftop, 108,979 connections | Rooftop capacity and connections | End 2025 | CEB, reported by pv magazine, 22 Sep 2026 |

The CEB figure for end 2025 is lower than the PUCSL figure for three months earlier. The likely reason is coverage (CEB alone, without LECO), but this is not confirmed. Ask in the utility interview.

**Decision for the paper:**

1. Capacity: "about 2,540 MW of rooftop solar (National System Operator, September 2026)". This is the proposal's number, and the source is now known.
2. Connections: "about 129,000 rooftop connections (PUCSL, end of September 2025)". Give the date every time. There is no September 2026 connection count.
3. Say **connections**, not households. The average is about 16 kW per connection, so the count includes shops and factories. The concept paper table says "129,000 rooftop-solar households". Change it.
4. Never put the two numbers in one sentence without their dates.
5. Growth: 25-30 MW of solar is being added each month (NSO statement).

## Edits to make (not made yet, because they change submitted wording)

| File | Edit |
|---|---|
| `03_Concept-Paper-Submission/Concept-Paper.md` section 1 | Remove the LKR 45.5 household sentence. Change "households" to "connections". Change "refusing new rooftop connections" to "restricting new approvals". Add the PUCSL "cannot see small batteries" reason. |
| `Concept-Paper.md` section 2 | Action 2 "Store it for the 6:30-10:30 pm window" becomes a lab-rig and simulation action, with the window 17:30-21:30. |
| `rooftop-vpp-clone/README.md` | Same changes. Needs a pull request reviewed by Tatiana or Senesh. |
| `docs/scope-decision.md` | Point 3 and the "If a battery is added" table cell |
| `docs/ui-ux-changes.md` | The battery bullet in "the rules changed" |
| `scheduler/tariffs.yaml` (task R4, Senesh) | Battery rate applies only above 250 kW. Window 17:30-21:30. |
