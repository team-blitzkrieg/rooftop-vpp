"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Line, LineChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { IconShield } from "@/components/household/icons";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { Button, Modal } from "@/components/household/ui";
import { useHomeData } from "@/components/household/use-home-data";
import { updateDemo, useDemo } from "@/lib/demo-store";
import { buildAlerts, todayKey } from "@/lib/household-derive";
import { zonedParts } from "@/lib/household";

export default function AlertDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const data = useHomeData();
  const demo = useDemo();
  const [contact, setContact] = useState(false);
  const alerts = buildAlerts(data.rows ?? [], data.zone);
  const alert = alerts.find((item) => item.id === params.id) ?? null;
  const seen = demo?.seenAlerts.includes(params.id) ?? false;
  const today = todayKey(data.zone);
  const chart = (data.rows ?? [])
    .filter((row) => row.target === "pv" && zonedParts(row.timestamp, data.zone).day === today)
    .map((row) => ({
      name: zonedParts(row.timestamp, data.zone).clock.slice(0, 2),
      pv: Number(row.value_kw),
      baseline: row.baseline_kw,
    }));

  function mark() {
    updateDemo((state) => ({
      ...state,
      seenAlerts: state.seenAlerts.includes(params.id) ? state.seenAlerts : [...state.seenAlerts, params.id],
    }));
    router.push("/household/alerts");
  }

  return (
    <Frame>
      <RequireDemo>
        <AppHeader title="Alert" back={{ href: "/household/alerts", label: "‹" }} simulated={data.snapshot.simulated} />
        <div className="hh-main">
          {!alert && data.rows ? (
            <section className="hh-card">
              <h2>This alert is no longer active</h2>
              <p className="hh-note">The forecast condition that created it is gone, or the id is unknown. Nothing was measured on site.</p>
            </section>
          ) : null}
          {alert ? (
            <>
              <div className="hh-pills">
                <span className={`hh-pill ${alert.level === "warning" ? "estimated" : "example"}`}>{alert.level}</span>
                <span className="hh-pill none">{seen ? "Seen" : "Active"}</span>
                <span className={`hh-pill ${alert.source.kind}`}>{alert.source.text}</span>
              </div>
              <h2>{alert.title}</h2>
              <section className="hh-card">
                <h2>Why we flagged this</h2>
                <p className="hh-note">{alert.detail}</p>
              </section>
              {chart.length ? (
                <section className="hh-card">
                  <h2>Today's PV forecast</h2>
                  <div style={{ height: 180 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chart}>
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} width={28} />
                        <Line dataKey="pv" stroke="#ff9800" dot={false} isAnimationActive />
                        <Line dataKey="baseline" stroke="#6b7280" strokeDasharray="4 4" dot={false} isAnimationActive />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </section>
              ) : null}
              <section className="hh-card">
                <h2>Safe next step</h2>
                <p className="hh-note">1. Look from the ground for new shade or heavy dust if you can do that safely.</p>
                <p className="hh-note">2. If it continues, contact your installer. This app does not store an installer.</p>
                <Button type="button" variant="secondary" onClick={() => setContact(true)}>Contact installer</Button>
              </section>
              <div className="hh-banner">
                <IconShield size={18} stroke="#b71c1c" />
                <div>
                  <strong>Don't open the inverter</strong>
                  <p>Inverters hold dangerous voltage even when switched off. Don't climb on the roof.</p>
                </div>
              </div>
              <Button type="button" variant="secondary" onClick={mark}>Mark as seen</Button>
            </>
          ) : null}
        </div>
      </RequireDemo>
      <Modal open={contact} title="No installer on file" onClose={() => setContact(false)}>
        <p className="hh-note">The site record has no installer name or phone. This button does not send a message.</p>
        <Button type="button" onClick={() => setContact(false)}>Close</Button>
      </Modal>
    </Frame>
  );
}
