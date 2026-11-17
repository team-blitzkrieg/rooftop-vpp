"use client";

import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { useHomeData } from "@/components/household/use-home-data";

export default function BatteryPage() {
  const data = useHomeData();
  return (
    <Frame>
      <RequireDemo>
        <AppHeader title="Battery scenario" back={{ href: "/household/settings", label: "‹" }} simulated={data.snapshot.simulated} />
        <div className="hh-main">
          <section className="hh-card">
            <h2>No battery model</h2>
            <p className="hh-note">The site record has no battery size, and the forecast has no battery series. A 5 kWh what-if is not calculated here.</p>
            <span className="hh-pill none">Not installed</span>
          </section>
          <p className="hh-note">This app never charges or discharges a battery.</p>
        </div>
      </RequireDemo>
    </Frame>
  );
}
