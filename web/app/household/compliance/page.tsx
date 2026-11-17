"use client";

import { AppHeader, Frame } from "@/components/household/shell";

export default function CompliancePage() {
  return (
    <Frame>
      <AppHeader title="Compliance" back={{ href: "/household/utility", label: "‹" }} simulated />
      <div className="hh-main">
        <section className="hh-card">
          <h2>No inverter settings were read</h2>
          <p className="hh-note">PUCSL has reported that much of the installed capacity is missing the updated protection settings. This pilot has no register reads, so every home is "need review", not "settings OK".</p>
          <span className="hh-pill estimated">not read</span>
        </section>
        <section className="hh-card">
          <h2>Seeded fault test</h2>
          <p className="hh-fine">fault-detect/results, simulated pvlib weather, not meters. Faults inserted by hand from 1 June 2025.</p>
          <p className="hh-note">Inverter off and half the panels: 5 of 5 sites, first alert in 3 days. Export stuck at 40%: 3 of 5, after 18 to 79 days. 15% dirt: not treated as detected. Healthy year: 2 of 5 sites raised a false alert.</p>
        </section>
      </div>
    </Frame>
  );
}
