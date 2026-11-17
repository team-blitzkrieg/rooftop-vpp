"use client";

import { useRouter } from "next/navigation";
import { IconPlan, IconSavings, IconShield, IconSun } from "@/components/household/icons";
import { RequireDemo } from "@/components/household/shell";
import { Button, Modal } from "@/components/household/ui";
import { useState } from "react";

export default function WelcomePage() {
  const router = useRouter();
  const [info, setInfo] = useState(false);
  return (
    <main className="hh">
      <RequireDemo onboarding>
        <div className="hh-auth">
          <div className="hh-mark">
            <IconSun size={32} stroke="#a14a07" />
          </div>
          <h1 className="hh-center-title">Rooftops to Power Plant</h1>
          <p className="hh-center-sub">Household pilot · Team Blitzkrieg</p>
          <section className="hh-card">
            <h2>What this pilot does</h2>
            <div className="hh-choice">
              <div className="hh-iconbox" style={{ background: "#ff980022" }}><IconSun size={18} stroke="#a14a07" /></div>
              <div className="hh-grow"><strong>See your solar, home use and grid flow</strong><span>From the latest forecast. Meter readings are not readable with this key.</span></div>
            </div>
            <div className="hh-choice">
              <div className="hh-iconbox" style={{ background: "#03a9f422" }}><IconPlan size={18} stroke="#0268a8" /></div>
              <div className="hh-grow"><strong>Get a daily plan</strong><span>Suggested times, from the PV forecast and loads you add on this browser.</span></div>
            </div>
            <div className="hh-choice">
              <div className="hh-iconbox" style={{ background: "#43a04722" }}><IconSavings size={18} stroke="#2a7130" /></div>
              <div className="hh-grow"><strong>Estimate savings</strong><span>In kWh. Rupee figures are labelled assumptions, not a bill.</span></div>
            </div>
          </section>
          <div className="hh-banner info">
            <IconShield size={18} stroke="#0268a8" />
            <div>
              <strong>Read-only: we never control your devices</strong>
              <p>Suggestions only. You decide what to switch on. Pausing a plan does not change equipment.</p>
            </div>
          </div>
          <div style={{ marginTop: "auto" }} />
          <Button type="button" onClick={() => router.push("/household/collect")}>Get started</Button>
          <button type="button" className="hh-btn ghost" onClick={() => setInfo(true)}>Pilot info sheet (2 min read)</button>
        </div>
      </RequireDemo>
      <Modal open={info} title="Pilot info" onClose={() => setInfo(false)}>
        <p className="hh-note">The app reads sites and forecasts with the public Supabase key. Loads, consent and pauses stay in this browser. Nothing sends a command to an inverter.</p>
        <Button type="button" onClick={() => setInfo(false)}>Close</Button>
      </Modal>
    </main>
  );
}
