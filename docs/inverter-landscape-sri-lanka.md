# Inverters in Sri Lanka: what we know and what we do not

Owner: Mithil Rajapakse. Written: 11 Nov 2026.

## Short answer

**There is no public brand-by-brand or model-by-model market share for Sri Lanka.** I searched the regulator (PUCSL), the utility (CEB), installer sites and trade press. None publishes it. Anyone quoting an exact percentage for Sri Lanka without a source is guessing.

What we do have: solid national totals, and a list of the brands installers say they sell most. Use those, label the list as "installer-reported, not measured", and get real counts from the utility (see "How to get real numbers").

## National facts (primary source)

Source: PUCSL, "Analysis on Rooftop Solar Integration and Industry Growth in Sri Lanka" (Dec 2025). https://www.pucsl.gov.lk/wp-content/uploads/2026/03/Analysis-on-Rooftop-Solar-Integration-Industry-Growth-in-Sri-Lanka.pdf

| Fact | Number |
|---|---|
| Rooftop solar connections, end Sep 2025 | 129,302 |
| Installed rooftop capacity, end Sep 2025 | about 2,090 MW |
| Capacity end 2024 | 1,401 MW |
| Capacity end 2023 | 812 MW |
| Growth in 2024 | 588 MW (the biggest year so far) |
| Rooftop share of generation, Q2 2025 | 10% (464 GWh) |
| Installed capacity that has the new post-blackout protection settings | **under 50%** |
| Share of all PUCSL consumer complaints that are about rooftop solar | over 50% |
| Solar companies registered with SLSEA since the programme began | over 1,100 |
| Of those, still operating in 2025 | about 600 |
| Statutory supply voltage | 230 V +/-6% (216.2 to 243.8 V) |

**Check this:** our proposal says 2,542 MW. PUCSL says about 2,090 MW at Sep 2025. The proposal figure may come from a later source (the proposal cites Sep 2026 articles). Find the source and put it in the concept paper. Do not leave two different numbers in circulation.

Average system size at Sep 2025: 2,090 MW / 129,302 = about 16 kW per connection. This average is pulled up by commercial systems. Homes are mostly 3 to 10 kW. The FiT bands (up to 10 kW, 10-40 kW, 40-250 kW) show where the split is.

## Brands reported as common (installer-reported, not measured)

Source: SolarMaster (Sri Lankan installer), "Best Solar Inverters in Sri Lanka 2026" (26 Jul 2026). https://solarmaster.lk/best-solar-inverters-in-sri-lanka-2026-brands-buying-guide/
This is a sales site. It names brands and gives opinions. It gives no counts or percentages.

| Brand | What the installer says | Typical home models | How a third-party box usually reads it (verify against manuals) |
|---|---|---|---|
| Huawei (FusionSolar) | "One of the most popular" in recent years. Strong app. Works best with its own LUNA battery. | SUN2000 string and hybrid series | Modbus TCP through the Smart Dongle on the home network, or RS485 on the inverter. Needs the installer to enable Modbus. Users report the dongle can be unstable. |
| SMA (Germany) | Premium, long life, open to third-party batteries. | Sunny Boy, Sunny Tripower | Modbus TCP (SunSpec) built in on most models. |
| Growatt | Budget end, "significant traction", many battery types. | MIN, MOD, SPH, SPF | RS485 Modbus RTU. Protocol document is public. |
| Solax Power | Popular mid-range hybrid choice among installers. | X1/X3 hybrid | Modbus over RS485 or LAN dongle. Varies by model. |
| Sungrow | "Growing presence". Competitive hybrids. | SH series hybrid, SG series | Modbus TCP through the WiNet dongle. |
| Fronius (Austria) | Premium, mostly commercial and quality-focused customers. | Primo, Symo GEN24 | Modbus TCP (SunSpec) and a local web interface. |

Warning from the same source and from PUCSL: many cheap, unbranded inverters are installed. They may lack anti-islanding protection. The edge unit must handle "unknown inverter" safely (see `edge-unit-plan-for-tatiana.md`).

A weak clue from the world market, not Sri Lanka: Huawei and Sungrow together had about 45% of the world inverter market in 2023 (BusinessWire/ResearchAndMarkets summary). Do not use this as a Sri Lankan figure.

## What this means for the build

1. Support **three brand families first**: Huawei, Growatt, and one of Solax/Sungrow/SMA, chosen by what the pilot homes and installers actually use.
2. Support a "SunSpec" style standard map where the inverter offers it, so SMA and Fronius come almost free.
3. Every other brand: the unit still works through an **external energy meter** (CT clamp) that does not depend on the inverter brand.

## How to get real numbers (do these)

| # | Action | Who | By |
|---|---|---|---|
| 1 | Ask the pilot home owner for the inverter make, model, firmware, size, battery yes/no, scheme. | Mithil | 14 Nov |
| 2 | In every installer interview, ask: "Out of your last 20 installs, how many were each brand? Single-phase or three-phase? With battery?" (Question 2 in `interview-script.md`.) | Mithil | 27 Nov |
| 3 | Ask the utility (CEB/LECO) and SLSEA for **anonymised counts** by inverter make and size band. Rooftop applications already list the inverter make and model. A table of counts needs no personal data. | Mithil | request by 16 Nov |
| 4 | Write the results into this file with a date and the source. Replace the "installer-reported" column with measured counts. | Mithil | 4 Dec |

Done when: this file has at least one measured number for brand share (from the utility) or a small installer survey with n >= 3 installers and the numbers shown.

## Other sources checked

- CEB, "Recommended Settings for Solar PV Inverters" (voltage and frequency settings). https://www.ceb.lk/front_img/img_reports/1742277909Solar_Inverter_settings.pdf (download and use as the reference for the settings check in `ui-ux-changes.md` item 15).
- PUCSL, Summary of Approved Feed-in Tariffs, Aug 2026. https://www.pucsl.gov.lk/wp-content/uploads/2026/08/Annex-2-Summary-of-Approved-Feed-in-Tariffs.pdf
- pv magazine, 22 Sep 2026, "Sri Lanka replaces net metering with feed-in tariffs for rooftop solar".
