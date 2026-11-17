"use client";

import Link from "next/link";
import summary from "../../../data/grid-summary.json";
import { AppHeader, Frame } from "@/components/household/shell";

type Row = (typeof summary)[number];

function risk(row: Row): "High" | "Watch" | "Low" {
  if (Number(row.transformer_overload_hours) > 0 || Number(row.over_voltage_hours) > 200) return "High";
  if (Number(row.over_voltage_hours) > 0) return "Watch";
  return "Low";
}

export default function UtilityPage() {
  const rows = summary.filter((row) => row.run.startsWith("share_") && row.period === "test_months" && row.case === "no_control");
  return (
    <Frame>
      <AppHeader title="Feeders" back={{ href: "/household/settings", label: "‹" }} simulated />
      <div className="hh-main">
        <p className="hh-note">Simulated neighbourhood from grid-sim/results/summary.csv. Not a real feeder. Advice mode does not control these homes.</p>
        <section className="hh-card">
          {rows.map((row) => {
            const level = risk(row);
            return (
              <Link key={row.run} href={`/household/utility/${row.solar_share}`} className="hh-choice">
                <span className="hh-grow">
                  <strong>{Math.round(Number(row.solar_share) * 100)}% solar · {row.homes_with_solar} homes</strong>
                  <span>{row.transformer_overload_hours} overload hours · max {row.transformer_max_loading_pct}% · {row.over_voltage_hours} over-voltage hours</span>
                </span>
                <span className={`hh-pill ${level === "High" ? "estimated" : level === "Watch" ? "example" : "measured"}`}>{level}</span>
              </Link>
            );
          })}
        </section>
        <Link className="hh-link" href="/household/fleet">Fleet total</Link>
        <Link className="hh-link" href="/household/compliance">Compliance</Link>
      </div>
    </Frame>
  );
}
