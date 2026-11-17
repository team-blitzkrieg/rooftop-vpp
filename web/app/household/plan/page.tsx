"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { Button, Modal, Segmented, Sheet } from "@/components/household/ui";
import { useHomeData } from "@/components/household/use-home-data";
import { updateDemo, useDemo } from "@/lib/demo-store";
import { buildPlan, dayLabel, todayKey } from "@/lib/household-derive";

export default function PlanPage() {
  const data = useHomeData();
  const demo = useDemo();
  const router = useRouter();
  const [tab, setTab] = useState<"plan" | "forecast" | "loads">("plan");
  const [sheet, setSheet] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [choice, setChoice] = useState<"skip" | "pause" | "replan">("pause");
  const [note, setNote] = useState("");
  const zone = data.zone;
  const today = todayKey(zone);
  const skipped = demo?.skipDay === today;
  const plan = buildPlan(data.rows ?? [], zone, demo?.loads ?? [], Boolean(demo?.paused) || skipped);

  function applyChoice() {
    if (choice === "skip") {
      updateDemo((state) => ({ ...state, skipDay: today }));
      setNote("Today's suggestions are hidden on this browser. Tomorrow still uses the forecast. No device changed.");
    } else if (choice === "pause") {
      setConfirm(true);
      return;
    } else {
      replan();
    }
    setSheet(false);
  }

  function replan() {
    updateDemo((state) => ({ ...state, skipDay: state.skipDay === today ? null : state.skipDay, paused: false }));
    setNote(`Rebuilt from the latest forecast${data.snapshot.issuedAt ? ` issued ${data.snapshot.issuedAt}` : ""}. Nothing was sent to a device.`);
  }

  function pause() {
    updateDemo((state) => ({ ...state, paused: true, pausedAt: new Date().toISOString() }));
    setConfirm(false);
    setSheet(false);
    setNote("Plans and tips are paused on this browser. Data display is unchanged and no device was contacted.");
  }

  return (
    <Frame>
      <RequireDemo>
        <AppHeader
          title="Daily plan"
          simulated={data.snapshot.simulated}
          offline={data.snapshot.mode === "offline"}
          action={<Button type="button" variant="secondary" className="slim" onClick={replan}>Replan</Button>}
        />
        <div className="hh-main">
          <p className="hh-fine">{dayLabel(today, zone)} · from the latest forecast · saved locally</p>
          <Segmented
            label="Plan sections"
            value={tab}
            onChange={(value) => {
              if (value === "forecast") router.push("/household/forecast");
              else if (value === "loads") router.push("/household/loads");
              else setTab(value);
            }}
            options={[
              { id: "plan", label: "Plan" },
              { id: "forecast", label: "Forecast" },
              { id: "loads", label: "Loads" },
            ]}
          />
          {data.rows === null || !demo ? <div className="hh-skel hh-skel-card" /> : null}
          {note ? <p className="hh-note">{note}</p> : null}
          {demo && data.rows && plan.status === "paused" ? (
            <section className="hh-card">
              <h2>{demo.paused ? "Participation is paused" : "Today is skipped"}</h2>
              <p className="hh-note">Suggestions are hidden. This does not switch anything off. Forecasts are still shown on Home.</p>
              <Button type="button" variant="secondary" onClick={() => updateDemo((state) => ({ ...state, paused: false, skipDay: null }))}>Resume suggestions</Button>
            </section>
          ) : null}
          {demo && data.rows && plan.status === "empty" ? (
            <section className="hh-card">
              <h2>No flexible loads yet</h2>
              <p className="hh-note">Add a load on this browser. The plan is only a suggestion.</p>
              <Link className="hh-btn primary" href="/household/loads/new">Add load</Link>
            </section>
          ) : null}
          {demo && data.rows && plan.status === "low-solar" ? (
            <section className="hh-card">
              <h2>We can't place these loads in the forecast</h2>
              <p className="hh-note">Forecast PV in range is {plan.pvKwh.toFixed(1)} kWh. Flexible loads add up to {plan.flexibleKwh.toFixed(1)} kWh, and none fit a high-PV block before their deadline.</p>
              <span className="hh-pill estimated">PLAN_LOW_SOLAR</span>
              <Link className="hh-btn secondary" href="/household/loads">Edit loads</Link>
            </section>
          ) : null}
          {demo && data.rows && plan.status === "ready" ? (
            <section className="hh-card">
              <h2>Suggestions</h2>
              {plan.placed.map((item) => (
                <Link key={item.load.id} href={`/household/loads/${item.load.id}`} className="hh-choice">
                  <div className="hh-grow">
                    <strong>{item.load.name}</strong>
                    <span>{item.start} – {item.end} · {item.pvKwh.toFixed(1)} kWh of forecast PV in the block</span>
                  </div>
                  <span className={`hh-pill ${item.status === "recommended" ? "measured" : item.status === "manual" ? "none" : "estimated"}`}>{item.status}</span>
                </Link>
              ))}
              <p className="hh-note">Suggestions only. You switch appliances on yourself. Nothing is controlled remotely.</p>
            </section>
          ) : null}
          <Button type="button" variant="secondary" onClick={() => setSheet(true)}>Override or pause</Button>
        </div>
      </RequireDemo>
      <Sheet open={sheet} title="Change today's plan" onClose={() => setSheet(false)}>
        <Choice id="skip" current={choice} onPick={setChoice} title="Skip today" detail="Hide today's suggestions. Tomorrow plans as usual." />
        <Choice id="pause" current={choice} onPick={setChoice} title="Pause participation" detail="No plans or tips until you resume. Forecasts stay visible. No device changes." />
        <Choice id="replan" current={choice} onPick={setChoice} title="Replan now" detail="Rebuild from the latest forecast already loaded." />
        <Button type="button" onClick={applyChoice}>Continue</Button>
      </Sheet>
      <Modal open={confirm} title="Pause participation?" onClose={() => setConfirm(false)}>
        <p className="hh-note">Daily suggestions stop on this browser. Savings stay a forecast estimate. Recording in Supabase is unchanged because this app only reads it. Nothing on your devices changes.</p>
        <div className="hh-actions">
          <Button type="button" variant="secondary" onClick={() => setConfirm(false)}>Cancel</Button>
          <Button type="button" onClick={pause}>Pause</Button>
        </div>
      </Modal>
    </Frame>
  );
}

function Choice({ id, current, onPick, title, detail }: { id: "skip" | "pause" | "replan"; current: string; onPick: (id: "skip" | "pause" | "replan") => void; title: string; detail: string }) {
  return (
    <button type="button" className="hh-choice" onClick={() => onPick(id)} aria-pressed={current === id}>
      <span className="hh-grow"><strong>{title}</strong><span>{detail}</span></span>
      <span className={`hh-check ${current === id ? "on" : ""}`} />
    </button>
  );
}
