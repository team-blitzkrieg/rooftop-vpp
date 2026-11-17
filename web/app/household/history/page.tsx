"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { AppHeader, Frame, RequireDemo, SiteTitle } from "@/components/household/shell";
import { Segmented, useReducedMotion } from "@/components/household/ui";
import { useHomeData } from "@/components/household/use-home-data";
import { addDays, dayLabel, hoursForDay, rangeDays, sumHours, todayKey, type HourBar } from "@/lib/household-derive";

type Span = "day" | "week" | "month" | "custom";

export default function HistoryPage() {
  const data = useHomeData();
  const animate = !useReducedMotion();
  const zone = data.zone;
  const today = todayKey(zone);
  const [span, setSpan] = useState<Span>("day");
  const [day, setDay] = useState(today);
  const [view, setView] = useState<"chart" | "table">("chart");
  const [from, setFrom] = useState(addDays(today, -6));
  const [to, setTo] = useState(today);
  const rows = data.rows ?? [];

  const days = useMemo(() => {
    if (span === "day") return [day];
    if (span === "week") return rangeDays(addDays(day, -6), day);
    if (span === "month") return rangeDays(`${day.slice(0, 8)}01`, day);
    return rangeDays(from, to);
  }, [span, day, from, to]);

  const hours = useMemo(() => days.flatMap((item) => hoursForDay(rows, zone, item)), [days, rows, zone]);
  const totals = sumHours(hours);
  const known = hours.filter((hour) => !hour.missing).length;
  const coverage = hours.length ? Math.round((known / hours.length) * 100) : 0;

  const chart = span === "day"
    ? hours.map((hour) => ({
        name: hour.label.slice(0, 2),
        solar: hour.missing ? null : hour.solarUsed,
        exported: hour.missing ? null : hour.exported,
        imported: hour.missing ? null : hour.imported,
      }))
    : days.map((item) => {
        const sum = sumHours(hoursForDay(rows, zone, item));
        return {
          name: item.slice(8),
          solar: sum?.solarUsed ?? null,
          exported: sum?.exported ?? null,
          imported: sum?.imported ?? null,
        };
      });

  return (
    <Frame>
      <RequireDemo>
        <AppHeader
          title="Energy history"
          back={{ href: "/household", label: "‹" }}
          simulated={data.snapshot.simulated}
          offline={data.snapshot.mode === "offline"}
        />
        <div className="hh-main">
          <Segmented
            label="History view"
            value={view}
            onChange={setView}
            options={[
              { id: "chart", label: "Chart" },
              { id: "table", label: "Table" },
            ]}
          />
          <Segmented
            label="Range"
            value={span}
            onChange={setSpan}
            options={[
              { id: "day", label: "Day" },
              { id: "week", label: "Week" },
              { id: "month", label: "Month" },
              { id: "custom", label: "Custom" },
            ]}
          />
          <div className="hh-row">
            <button type="button" className="hh-icon-btn" onClick={() => setDay(addDays(day, -1))} aria-label="Previous day">‹</button>
            <strong>{dayLabel(day, zone)}</strong>
            <button type="button" className="hh-icon-btn" onClick={() => setDay(addDays(day, 1))} aria-label="Next day">›</button>
          </div>
          {span === "custom" ? (
            <div className="hh-split">
              <div className="hh-field">
                <label htmlFor="from">From</label>
                <div className="hh-input"><input id="from" type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></div>
              </div>
              <div className="hh-field">
                <label htmlFor="to">To</label>
                <div className="hh-input"><input id="to" type="date" value={to} onChange={(event) => setTo(event.target.value)} /></div>
              </div>
            </div>
          ) : null}
          {data.rows === null ? <div className="hh-skel hh-skel-card" /> : null}
          {view === "chart" && data.rows ? (
            <section className="hh-card">
              <div className="hh-row"><h2>Hourly energy</h2><span className="hh-fine">kWh · forecast</span></div>
              <div style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart}>
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={span === "day" ? 2 : 0} />
                    <YAxis tick={{ fontSize: 10 }} width={28} />
                    <Bar dataKey="solar" stackId="e" fill="#ff9800" isAnimationActive={animate} animationDuration={800} animationEasing="ease-out" />
                    <Bar dataKey="exported" stackId="e" fill="#a280db" isAnimationActive={animate} animationDuration={800} animationEasing="ease-out" />
                    <Bar dataKey="imported" stackId="e" fill="#03a9f4" isAnimationActive={animate} animationDuration={800} animationEasing="ease-out" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="hh-fine">Orange solar used at home · purple exported · blue imported. Gaps are missing forecast hours, not a meter reading of zero.</p>
            </section>
          ) : null}
          {view === "table" && data.rows ? <HourTable hours={span === "day" ? hours : []} days={span === "day" ? [] : days} rows={rows} zone={zone} /> : null}
          <section className="hh-card">
            <div className="hh-row">
              <h2>Forecast coverage</h2>
              <strong>{known} of {hours.length} ({coverage}%)</strong>
            </div>
            <p className="hh-note">{coverage}% is {known} divided by {hours.length}, for the {span} range on this screen. It is forecast hours, not a meter, and not a separate 7-day figure.</p>
          </section>
          <div className="hh-stats">
            <Mini label="Solar used" value={totals?.solarUsed ?? null} />
            <Mini label="Demand" value={totals?.demand ?? null} />
            <Mini label="Exported" value={totals?.exported ?? null} />
            <Mini label="Imported" value={totals?.imported ?? null} />
          </div>
          <p className="hh-local">Saved on this screen from the latest forecast only. {SiteTitle({ site: data.site })}</p>
          <Link className="hh-link" href="/household/forecast">Open solar forecast</Link>
        </div>
      </RequireDemo>
    </Frame>
  );
}

function Mini({ label, value }: { label: string; value: number | null }) {
  return (
    <section className="hh-card">
      <p className="hh-fine">{label}</p>
      <strong>{value === null ? "—" : `${value.toFixed(1)} kWh`}</strong>
    </section>
  );
}

function HourTable({ hours, days, rows, zone }: { hours: HourBar[]; days: string[]; rows: NonNullable<ReturnType<typeof useHomeData>["rows"]>; zone: string }) {
  if (hours.length) {
    return (
      <section className="hh-card">
        <h2>Hourly values</h2>
        <table className="hh-table">
          <thead>
            <tr><th>Hour</th><th>Solar</th><th>Used</th><th>Export</th><th>Import</th></tr>
          </thead>
          <tbody>
            {hours.map((hour) => hour.missing ? (
              <tr key={hour.key}><td>{hour.label}</td><td className="hh-miss" colSpan={4}>No forecast</td></tr>
            ) : (
              <tr key={hour.key}>
                <td>{hour.label}</td>
                <td>{hour.pv === null ? "—" : hour.pv.toFixed(2)}</td>
                <td>{hour.demand === null ? "—" : hour.demand.toFixed(2)}</td>
                <td>{hour.exported.toFixed(2)}</td>
                <td>{hour.imported.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    );
  }
  return (
    <section className="hh-card">
      <h2>Daily values</h2>
      <table className="hh-table">
        <thead>
          <tr><th>Day</th><th>Solar</th><th>Export</th><th>Import</th></tr>
        </thead>
        <tbody>
          {days.map((item) => {
            const sum = sumHours(hoursForDay(rows, zone, item));
            return (
              <tr key={item}>
                <td>{item.slice(5)}</td>
                <td>{sum ? sum.solarUsed.toFixed(1) : "No forecast"}</td>
                <td>{sum ? sum.exported.toFixed(1) : "—"}</td>
                <td>{sum ? sum.imported.toFixed(1) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
