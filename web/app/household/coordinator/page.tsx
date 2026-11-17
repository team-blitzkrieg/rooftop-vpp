"use client";

import { AppHeader, Frame } from "@/components/household/shell";
import { useHomeData } from "@/components/household/use-home-data";
import { useDemo } from "@/lib/demo-store";

export default function CoordinatorPage() {
  const data = useHomeData();
  const demo = useDemo();
  return (
    <Frame>
      <AppHeader title="Sites" back={{ href: "/household/settings", label: "‹" }} simulated={data.snapshot.simulated} />
      <div className="hh-main">
        <p className="hh-note">Assignment and cases are not in the database. Consent status is this browser's demo only.</p>
        <section className="hh-card">
          <h2>Homes</h2>
          {data.sites.length === 0 ? <p className="hh-note">No sites returned.</p> : data.sites.map((site) => (
            <div key={site.site_id} className="hh-choice">
              <span className="hh-grow">
                <strong>{site.name || site.site_id}</strong>
                <span>Unassigned · no open case stored · {site.site_id === data.siteId && demo?.consent ? "consent on this browser" : "no consent record"}</span>
              </span>
            </div>
          ))}
        </section>
      </div>
    </Frame>
  );
}
