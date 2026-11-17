"use client";

import { useParams } from "next/navigation";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import day from "../../../../data/feeder-day.json";
import summary from "../../../../data/grid-summary.json";
import { AppHeader, Frame } from "@/components/household/shell";
import { useReducedMotion } from "@/components/household/ui";

export default function FeederPage() {
  const params = useParams<{ share: string }>();
  const animate = !useReducedMotion();
  const share = params.share;
  const row = summary.find((item) => item.solar_share === share && item.period === "test_months" && item.case === "no_control");
  const showHours = share === "0.6";
  return (
    <Frame>
      <AppHeader title="Feeder" back={{ href: "/household/utility", label: "‹" }} simulated />
      <div className="hh-main">
        {!row ? <p className="hh-note">That solar share is not in the committed summary.</p> : (
          <section className="hh-card">
            <h2>{Math.round(Number(share) * 100)}% solar, no control</h2>
            <p className="hh-note">Test months. Transformer max loading {row.transformer_max_loading_pct}%. Over-voltage hours {row.over_voltage_hours}. Highest voltage {row.max_voltage_v} V. Simulated.</p>
          </section>
        )}
        {showHours ? (
          <section className="hh-card">
            <h2>Highest-voltage day · {day.day}</h2>
            <p className="hh-fine">{day.note} Blue bars are transformer loading, in percent. The peak voltage is written under the chart, so colour is not the only cue.</p>
            <div style={{ height: 220 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={day.hours}>
                  <XAxis dataKey="hour" tick={{ fontSize: 10 }} interval={2} />
                  <YAxis tick={{ fontSize: 10 }} width={28} />
                  <Bar dataKey="loadingPct" fill="#0277bd" isAnimationActive={animate} animationDuration={800} name="Loading %" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="hh-note">Peak voltage that day {Math.max(...day.hours.map((hour) => hour.voltagePu)).toFixed(3)} pu. Loading is percent of the simulated transformer.</p>
          </section>
        ) : <p className="hh-note">An hourly series is committed only for the 60% run (hourly_share_60.csv).</p>}
      </div>
    </Frame>
  );
}
