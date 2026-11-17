"use client";

import ceb from "../../../../fault-detect/ceb_inverter_settings.json";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";

const ROWS = Object.entries(ceb.settings).slice(0, 8);

export default function SettingsCheckPage() {
  return (
    <Frame>
      <RequireDemo>
        <AppHeader title="Inverter settings" back={{ href: "/household/settings", label: "‹" }} />
        <div className="hh-main">
          <section className="hh-card">
            <div className="hh-row"><h2>Settings need review</h2><span className="hh-pill estimated">not read</span></div>
            <p className="hh-note">The edge unit has not read this inverter. Every CEB check below is not_read. That is a review, not a pass.</p>
          </section>
          <section className="hh-card">
            <h2>CEB recommended values</h2>
            <p className="hh-fine">{ceb.source.title}. Check the PDF before anyone uses these on a real inverter.</p>
            {ROWS.map(([key, setting]) => (
              <div key={key} className="hh-row">
                <span className="hh-grow"><strong>{key}</strong><span>{setting.meaning}</span></span>
                <span className="hh-fine">{String(setting.value)}</span>
              </div>
            ))}
          </section>
        </div>
      </RequireDemo>
    </Frame>
  );
}
