"use client";

import { AppHeader, Frame } from "@/components/household/shell";

export default function HelpPage() {
  return (
    <Frame>
      <AppHeader title="Help and contact" back={{ href: "/household/settings", label: "‹" }} />
      <div className="hh-main">
        <section className="hh-card">
          <h2>No contact is stored</h2>
          <p className="hh-note">This demo does not email a pilot team and does not store an installer name or phone. Forgot-password and credential requests on the sign-in screen explain that too.</p>
          <p className="hh-note">Mode is Advice. The app never writes to an inverter. Bench control stays on the lab rig, not in a home.</p>
        </section>
        <p className="hh-note">Pilot info: the app reads sites and forecasts with the public key. Loads, consent and pauses stay in this browser.</p>
      </div>
    </Frame>
  );
}
