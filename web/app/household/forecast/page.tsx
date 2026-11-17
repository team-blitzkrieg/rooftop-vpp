"use client";

import { useMemo, useState } from "react";
import { Line, LineChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { CountUp, Segmented, useReducedMotion } from "@/components/household/ui";
import { useHomeData } from "@/components/household/use-home-data";
import { sourceBadge, zonedParts } from "@/lib/household";
import { addDays, todayKey } from "@/lib/household-derive";
import { IconSun } from "@/components/household/icons";
import Link from "next/link";

type Span = "today" | "tomorrow" | "week";

export default function ForecastPage() {
  const data = useHomeData();
  const animate = !useReducedMotion();
  const zone = data.zone;
  const today = todayKey(zone);
  const [span, setSpan] = useState<Span>("today");
  const rows = data.rows ?? [];
  const day = span === "tomorrow" ? addDays(today, 1) : today;

  const points = useMemo(() => {
    const pv = rows.filter((row) => row.target === "pv");
    if (span === "week") {
      return Array.from({ length: 7 }, (_, index) => {
        const key = addDays(today, index);
        const dayRows = pv.filter((row) => zonedParts(row.timestamp, zone).day === key);
        const value = dayRows.reduce((sum, row) => sum + Number(row.value_kw), 0);
        const baseline = dayRows.reduce((sum, row) => sum + (row.baseline_kw ?? 0), 0);
        return { name: key.slice(8), pv: dayRows.length ? value : null, baseline: dayRows.some((row) => row.baseline_kw !== null) ? baseline : null };
      });
    }
    return Array.from({ length: 24 }, (_, hour) => {
      const key = `${day}-${String(hour).padStart(2, "0")}`;
      const row = pv.find((item) => zonedParts(item.timestamp, zone).key === key);
      return {
        name: String(hour).padStart(2, "0"),
        pv: row ? Number(row.value_kw) : null,
        baseline: row?.baseline_kw ?? null,
      };
    });
  }, [rows, span, today, day, zone]);

  const total = points.reduce((sum, point) => sum + (point.pv ?? 0), 0);
  const hasPoint = points.some((point) => point.pv !== null);
  const badge = rows.find((row) => row.target === "pv");
  const source = badge ? sourceBadge(badge) : null;

  return (
    <Frame>
      <RequireDemo>
        <AppHeader title="Solar forecast" back={{ href: "/household", label: "‹" }} simulated={data.snapshot.simulated} offline={data.snapshot.mode === "offline"} />
        <div className="hh-main">
          <Segmented
            label="Forecast range"
            value={span}
            onChange={setSpan}
            options={[
              { id: "today", label: "Today" },
              { id: "tomorrow", label: "Tomorrow" },
              { id: "week", label: "7 days" },
            ]}
          />
          {data.rows === null ? <div className="hh-skel hh-skel-card" /> : (
            <section className="hh-card">
              <div className="hh-row">
                <h2>Forecast · kW</h2>
                {source ? <span className={`hh-pill ${source.kind}`}>{source.text}</span> : null}
              </div>
              <div style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={points}>
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={span === "week" ? 0 : 2} />
                    <YAxis tick={{ fontSize: 10 }} width={28} />
                    <Line type="monotone" dataKey="pv" stroke="#ff9800" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={animate} animationDuration={900} animationEasing="ease-out" />
                    <Line type="monotone" dataKey="baseline" stroke="#6b7280" strokeDasharray="4 4" dot={false} connectNulls={false} isAnimationActive={animate} animationDuration={900} animationEasing="ease-out" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="hh-fine">Orange is the PV forecast. The dashed line is baseline_kw when the row has one. There is no uncertainty band in this data.</p>
            </section>
          )}
          <div className="hh-metrics">
            <section className="hh-card">
              <p className="hh-fine">Expected {span === "week" ? "7 days" : span}</p>
              <strong><CountUp value={hasPoint ? total : null} suffix="kWh" /></strong>
              {source ? <span className={`hh-pill ${source.kind}`}>{source.text}</span> : null}
            </section>
            <section className="hh-card">
              <p className="hh-fine">Measured so far</p>
              <strong>—</strong>
              <span className="hh-pill none">Not available</span>
            </section>
          </div>
          <Link href="/household/plan" className="hh-plain">
            <section className="hh-card">
              <div className="hh-row">
                <div className="hh-iconbox" style={{ background: "#ff980022" }}><IconSun size={18} stroke="#a14a07" /></div>
                <div className="hh-grow">
                  <span className="hh-fine">Best window in the forecast</span>
                  <strong>{data.snapshot.window ? data.snapshot.window.label : "—"}</strong>
                </div>
                <span>›</span>
              </div>
            </section>
          </Link>
          <p className="hh-note">Treat the best window as a suggestion from the forecast, not a guarantee. Passing clouds are not in these rows.</p>
        </div>
      </RequireDemo>
    </Frame>
  );
}
