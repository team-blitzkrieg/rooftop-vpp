"use client";

import summary from "../../../data/grid-summary.json";
import { AppHeader, Frame } from "@/components/household/shell";

export default function FleetPage() {
  const row = summary.find((item) => item.run === "share_60" && item.period === "full_year" && item.case === "no_control");
  return (
    <Frame>
      <AppHeader title="Fleet total" back={{ href: "/household/utility", label: "‹" }} simulated />
      <div className="hh-main">
        <section className="hh-card">
          <h2>One simulated plant</h2>
          <p className="hh-note">The 60% case treated as a single plant. Scenarios are not added together.</p>
          {row ? (
            <>
              <p className="hh-note">{row.homes_with_solar} homes with solar · {row.solar_kw_installed} kW installed.</p>
              <p className="hh-note">Solar available {Number(row.solar_available_kwh).toLocaleString("en-LK")} kWh over the simulated year. Nothing was held back in the no-control case.</p>
              <span className="hh-pill simulated">Simulated</span>
            </>
          ) : <p className="hh-note">The 60% full-year row is missing from the summary file.</p>}
        </section>
      </div>
    </Frame>
  );
}
