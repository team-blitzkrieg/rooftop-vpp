"use client";

import Link from "next/link";
import { useState } from "react";
import { IconAlert, IconCheck, IconInfo } from "@/components/household/icons";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { Segmented } from "@/components/household/ui";
import { useHomeData } from "@/components/household/use-home-data";
import { useDemo } from "@/lib/demo-store";
import { buildAlerts } from "@/lib/household-derive";

export default function AlertsPage() {
  const data = useHomeData();
  const demo = useDemo();
  const [filter, setFilter] = useState<"all" | "active" | "seen">("all");
  const alerts = buildAlerts(data.rows ?? [], data.zone);
  const seen = new Set(demo?.seenAlerts ?? []);
  const active = alerts.filter((alert) => !seen.has(alert.id));
  const resolved = alerts.filter((alert) => seen.has(alert.id));
  const shown = filter === "active" ? active : filter === "seen" ? resolved : alerts;

  return (
    <Frame>
      <RequireDemo>
        <AppHeader title="Alerts" simulated={data.snapshot.simulated} offline={data.snapshot.mode === "offline"} action={<span className={active.length ? "hh-help" : "hh-fine"}>{active.length} active</span>} />
        <div className="hh-main">
          <Segmented
            label="Alert filter"
            value={filter}
            onChange={setFilter}
            options={[
              { id: "all", label: `All ${alerts.length}` },
              { id: "active", label: `Active ${active.length}` },
              { id: "seen", label: `Seen ${resolved.length}` },
            ]}
          />
          {demo && !demo.notifyAlerts ? <p className="hh-note">Forecast alerts are hidden on this browser. Turn them on under Notifications. The conditions are unchanged.</p> : null}
          {data.rows === null ? <div className="hh-skel hh-skel-card" /> : null}
          {data.rows && demo?.notifyAlerts !== false && shown.length === 0 ? (
            <section className="hh-card" style={{ textAlign: "center", padding: 28 }}>
              <div className="hh-iconbox" style={{ background: "#43a04722", margin: "0 auto", width: 56, height: 56, borderRadius: 28 }}>
                <IconCheck size={26} stroke="#2a7130" />
              </div>
              <h2>All good</h2>
              <p className="hh-note">No {filter === "seen" ? "seen" : "active"} forecast alerts. These checks use the forecast only. They are not inverter alarms.</p>
              {filter !== "seen" && resolved.length ? (
                <button type="button" className="hh-btn ghost" onClick={() => setFilter("seen")}>View seen alerts</button>
              ) : null}
            </section>
          ) : null}
          {demo?.notifyAlerts !== false && shown.length ? (
            <section className="hh-card">
              {shown.map((alert) => (
                <Link key={alert.id} href={`/household/alerts/${alert.id}`} className="hh-choice">
                  {alert.level === "warning" ? <IconAlert size={18} stroke="#a14a07" /> : <IconInfo size={18} stroke="#0268a8" />}
                  <span className="hh-grow">
                    <strong>{alert.title}</strong>
                    <span>{seen.has(alert.id) ? "Seen" : "Active"} · {alert.source.text}</span>
                  </span>
                  <span>›</span>
                </Link>
              ))}
            </section>
          ) : null}
          <p className="hh-note">An alert is active only while its forecast condition is still true. We will never ask you to open or reset the inverter.</p>
        </div>
      </RequireDemo>
    </Frame>
  );
}
