# Concept paper outline

Owner: Mithil Rajapakse. Pipeline task W1. Draft: 11 Nov 2026. Team agrees it by Tue 15 Dec.

Limit: 5 pages, counted strictly until the organisers say otherwise (`challenge-rules.md`).
Section numbers and owners follow `03_Concept-Paper-Submission/Concept-Paper.md` and `Team-Tasks.md`. This replaces the 10-section skeleton in `project-pipeline.md`, which does not fit in 5 pages.

Lead message (Option C, if the team confirms it on 20 Nov):
**"Sri Lanka cannot see or check 2,540 MW of rooftop solar. A low-cost box and AI software make it visible, check its safety settings, catch faults, and show the control that becomes possible."**

| # | Section | Owner | Pages | One-line note | Evidence that goes here | Judging criterion |
|---|---|---|---|---|---|---|
| 1 | Problem and beneficiaries | Mithil | 0.6 | Fast growth, no visibility, under half of capacity has the safety settings, new approvals restricted. Who is affected. | PUCSL Dec 2025; NSO Sep 2026; `facts-check.md` | Impact |
| 2 | Solution and system overview | Tatiana (hardware, diagram), Senesh (software paragraph) | 0.8 | Edge Unit, three tiers. Homes are read-only: watch, check, advise. Control on the lab rig and in simulation only. | `edge-unit-plan-for-tatiana.md`, `scope-decision.md`, one block diagram | Innovation, feasibility |
| 3 | AI implementation | Senesh, with Mithil | 0.8 | Three AI jobs, each with a baseline and a score: forecast (LightGBM vs yesterday-same-hour), voltage model (learned from measurements), fault and settings detection. Generative AI disclosure. | Forecast score table (S3, S5); voltage model error 0.04 V; `fault-detect/README.md` | AI implementation |
| 4 | Data | Senesh | 0.4 | Source, rights, cleaning, split by date, what is simulated. Say plainly: no measured rooftop data yet. | `data/README.md`, metadata files | AI implementation |
| 5 | Prototype and results | Tatiana (Edge Unit, rig), Mithil (simulation, fault test) | 1.0 | The main result: over-voltage and overload hours with and without the export limit, and its cost. The fault test. The Edge Unit simulator and first read. | `grid-sim/results/control_result.png` and table; `fault-detect/results/` | Feasibility, AI implementation |
| 6 | Impact and special-consideration areas | Mithil | 0.5 | Income protected per home, grid safety, fuel imports, public service, district-level pilot. Every estimate labelled. | `Mithil-sections-draft.md` section 6 | Impact |
| 7 | Business model and scalability | Tatiana | 0.4 | Parts cost per tier, who pays (from interview question 6), installer channel, utility service. | Parts list, interviews | Feasibility |
| 8 | Risks, limits and next steps | Tatiana (all review) | 0.3 | Rule changes, approvals, simulated data, balanced model, inverter brands. February pilot plan and what it measures. | `grid-sim/README.md` limits, risk table in the pipeline | Feasibility |
| | References | Mithil | 0.2 | Numbered list, primary sources first | `Solar-Proposal-Sources.md`, `facts-check.md` | |

Total: 5.0 pages.

## Where "what we learned from interviews" goes

No separate section. One sentence each in sections 1 (problem is real), 7 (who pays) and 8 (approvals). If the interviews change the plan, say so in section 2.

## Figures (3 at most)

1. System block diagram (section 2). Tatiana.
2. Over-voltage and overload hours with and without the limit (section 5). Done: `grid-sim/results/control_result.png`.
3. One app or utility dashboard screen (section 5 or 2). Senesh.

## Numbers that must not appear

See `facts-check.md`. In short: no LKR 45.53 for homes, no "6:30-10:30 pm", no "129,000 households" (say connections), no "365 GWh" or "USD 65-75 million" without the "if home batteries get a tariff" label.

## Panel questions checklist

Copy the 10 questions from `challenge-rules.md` into the last review (W9) and tick each one against a section.
