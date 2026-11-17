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
            <h2>No home battery rate</h2>
            <p className="hh-note">The published solar-plus-battery tariff is only for plants above 250 kW. A home does not earn that rate, and this app does not tell anyone to store midday solar to sell in the evening.</p>
            <p className="hh-note">The prioritized window in that large-plant tariff is reported as 17:30 to 21:30, and it can move. It is not a home tariff.</p>
            <span className="hh-pill none">Not installed</span>
          </section>
          <p className="hh-note">This app never charges or discharges a battery. Advice mode only.</p>
        </div>
      </RequireDemo>
    </Frame>
  );
}
