"use client";

import Link from "next/link";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { useHomeData } from "@/components/household/use-home-data";
import { loadEnergyKwh, updateDemo, useDemo, type Load } from "@/lib/demo-store";

export default function LoadsPage() {
  const data = useHomeData();
  const demo = useDemo();
  const loads = demo?.loads ?? [];

  function setManual(load: Load, manualOnly: boolean) {
    updateDemo((state) => ({
      ...state,
      loads: state.loads.map((item) => (item.id === load.id ? { ...item, manualOnly } : item)),
    }));
  }

  return (
    <Frame>
      <RequireDemo>
        <AppHeader
          title="Flexible loads"
          back={{ href: "/household/plan", label: "‹" }}
          simulated={data.snapshot.simulated}
          action={<Link className="hh-btn primary slim" href="/household/loads/new">Add load</Link>}
        />
        <div className="hh-main">
          <p className="hh-note">Appliances you can run at flexible times. Manual-only keeps an appliance out of the plan. Saved in this browser.</p>
          {loads.length === 0 ? (
            <section className="hh-card" style={{ textAlign: "center" }}>
              <h2>No flexible loads yet</h2>
              <p className="hh-note">Add a washing machine, pump or charger to get a daily plan.</p>
              <Link className="hh-btn secondary" href="/household/loads/new">Add load</Link>
            </section>
          ) : (
            <section className="hh-card">
              {loads.map((load) => (
                <div key={load.id} className="hh-choice">
                  <Link href={`/household/loads/${load.id}`} className="hh-grow hh-plain">
                    <strong>{load.name}</strong>
                    <span>{load.watts} W · {load.minutes} min · {loadEnergyKwh(load).toFixed(1)} kWh estimated · by {load.deadline}</span>
                  </Link>
                  <button type="button" className={`hh-toggle ${load.manualOnly ? "" : "on"}`} aria-label={load.manualOnly ? "Include in plan" : "Keep out of plan"} onClick={() => setManual(load, !load.manualOnly)}>
                    <i />
                  </button>
                </div>
              ))}
            </section>
          )}
          <p className="hh-local">Power values are what you entered. This edge data cannot measure a single appliance.</p>
        </div>
      </RequireDemo>
    </Frame>
  );
}
