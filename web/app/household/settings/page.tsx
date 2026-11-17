"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { Button, Modal } from "@/components/household/ui";
import { useHomeData } from "@/components/household/use-home-data";
import { updateDemo, useDemo } from "@/lib/demo-store";
import { browserSupabase } from "@/lib/supabase";

export default function SettingsPage() {
  const data = useHomeData();
  const demo = useDemo();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [phrase, setPhrase] = useState("");
  const [error, setError] = useState("");

  function withdraw() {
    if (phrase.trim() !== "WITHDRAW") {
      setError("Type WITHDRAW to confirm.");
      return;
    }
    const email = demo?.session?.email ?? "";
    const at = new Date();
    const deleteBy = new Date(at.getTime() + 30 * 24 * 60 * 60 * 1000);
    updateDemo((state) => ({
      ...state,
      withdrawReceipt: {
        id: `WD-${at.getFullYear()}-${String(at.getMonth() + 1).padStart(2, "0")}${String(at.getDate()).padStart(2, "0")}`,
        email,
        at: at.toISOString(),
        deleteBy: deleteBy.toISOString(),
      },
    }));
    router.push("/household/withdrawn");
  }

  return (
    <Frame>
      <RequireDemo>
        <AppHeader title="Privacy and participation" simulated={data.snapshot.simulated} offline={data.snapshot.mode === "offline"} />
        <div className="hh-main">
          <p className="hh-fine">DATA WE SHOW</p>
          <section className="hh-card">
            <Row label="Solar output" detail="From the PV forecast" tag={demo?.consent?.scopes.solar ? "Forecast" : "Hidden"} />
            <Row label="Grid import and export" detail="Derived from the forecast" tag={demo?.consent?.scopes.grid ? "Forecast" : "Hidden"} />
            <Row label="Household use" detail="From the demand forecast" tag={demo?.consent?.scopes.home ? "Forecast" : "Hidden"} />
            <Row label="Appliance-level use" detail="Not collected" tag="Not available" />
          </section>
          <p className="hh-note">
            {demo?.consent ? `Local consent ${demo.consent.version} · ${new Date(demo.consent.agreedAt).toLocaleString("en-GB")}` : "No local consent saved."}{" "}
            <Link className="hh-link" href="/household/receipt">View receipt</Link>
          </p>
          <section className="hh-card">
            <div className="hh-row">
              <div>
                <strong>Pause participation</strong>
                <p className="hh-fine">Stops suggestions. Forecasts stay visible. No device changes.</p>
              </div>
              <button
                type="button"
                className={`hh-toggle ${demo?.paused ? "on" : ""}`}
                aria-pressed={Boolean(demo?.paused)}
                onClick={() => updateDemo((state) => ({ ...state, paused: !state.paused, pausedAt: state.paused ? null : new Date().toISOString() }))}
              >
                <i />
              </button>
            </div>
          </section>
          <section className="hh-card">
            <Link className="hh-row-link" href="/household/profile"><span className="hh-grow"><strong>Site profile</strong><span>{demo?.profile ? `${demo.profile.scheme} · ${demo.profile.systemKw || "—"} kW · pending` : "Not saved on this browser"}</span></span><span>›</span></Link>
            <Link className="hh-row-link" href="/household/battery"><span className="hh-grow"><strong>Battery scenario</strong><span>Homes do not get the large-plant battery rate</span></span><span>›</span></Link>
            <Link className="hh-row-link" href="/household/settings-check"><span className="hh-grow"><strong>Inverter settings</strong><span>Not read from a device</span></span><span>›</span></Link>
            <Link className="hh-row-link" href="/household/help"><span className="hh-grow"><strong>Help and contact</strong><span>No installer is stored</span></span><span>›</span></Link>
            <Link className="hh-row-link" href="/household/notifications"><span className="hh-grow"><strong>Notifications</strong><span>{demo?.notifyAlerts ? "Forecast alerts on" : "Forecast alerts off"}</span></span><span>›</span></Link>
            <Link className="hh-row-link" href="/household/utility"><span className="hh-grow"><strong>Utility view</strong><span>Simulated feeder results</span></span><span>›</span></Link>
            <Link className="hh-row-link" href="/household/coordinator"><span className="hh-grow"><strong>Coordinator</strong><span>Sites, assignments, and cases</span></span><span>›</span></Link>
            <Link className="hh-row-link" href="/household/technician"><span className="hh-grow"><strong>Technician</strong><span>Brands, registers, safety</span></span><span>›</span></Link>
            <Link className="hh-row-link" href="/household/components"><span className="hh-grow"><strong>Component sheet</strong><span>Shared controls used in this app</span></span><span>›</span></Link>
            <div className="hh-row-link"><span className="hh-grow"><strong>Account</strong><span>{demo?.session?.email}</span></span></div>
          </section>
          <Button type="button" variant="danger-outline" onClick={() => setOpen(true)}>Withdraw from pilot</Button>
          <p className="hh-local">{demo?.session?.mode === "auth" ? "Signed in with an email code. Advice only." : "Demo sign-in. Stored on this browser."} Withdrawing does not delete forecasts and does not contact a device.</p>
          <button type="button" className="hh-btn ghost" onClick={() => { void browserSupabase()?.auth.signOut(); updateDemo((state) => ({ ...state, session: null })); router.push("/household/sign-in"); }}>Sign out</button>
        </div>
      </RequireDemo>
      <Modal open={open} title="Withdraw from the pilot?" onClose={() => setOpen(false)}>
        <ul className="hh-note">
          <li>Clears loads, pauses, consent and the session on this browser.</li>
          <li>Does not delete forecast rows.</li>
          <li>Does not stop an edge unit, because this app never starts one.</li>
          <li>Signs you out of this demo.</li>
          <li>{demo?.session?.mode === "auth" ? "The consent row is marked withdrawn. Forecast rows stay." : demo?.consent?.scopes.totals ? "Anonymised totals were included in the consent on this browser. Nothing was written to Supabase." : "Anonymised totals were not consented, and none are kept."}</li>
        </ul>
        <p className="hh-note">Your solar system is not affected. Type WITHDRAW to confirm.</p>
        <div className="hh-input">
          <input aria-label="Type WITHDRAW" value={phrase} onChange={(event) => setPhrase(event.target.value)} placeholder="WITHDRAW" />
        </div>
        {error ? <p className="hh-help">{error}</p> : null}
        <div className="hh-actions">
          <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
          <Button type="button" variant="danger" onClick={withdraw}>Withdraw</Button>
        </div>
      </Modal>
    </Frame>
  );
}

function Row({ label, detail, tag }: { label: string; detail: string; tag: string }) {
  return (
    <div className="hh-row" style={{ alignItems: "flex-start" }}>
      <div><strong>{label}</strong><p className="hh-fine">{detail}</p></div>
      <span className={`hh-pill ${tag === "Not available" || tag === "Hidden" ? "none" : "example"}`}>{tag}</span>
    </div>
  );
}
