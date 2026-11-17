"use client";

import { useState } from "react";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { CountUp, Segmented } from "@/components/household/ui";
import { useHomeData } from "@/components/household/use-home-data";
import { useDemo } from "@/lib/demo-store";
import { addDays, hoursForDay, rangeDays, sumHours, todayKey } from "@/lib/household-derive";

export default function SavingsPage() {
  const data = useHomeData();
  const demo = useDemo();
  const zone = data.zone;
  const today = todayKey(zone);
  const [span, setSpan] = useState<"week" | "month" | "pilot">("month");
  const [open, setOpen] = useState(false);
  const [rate, setRate] = useState("");
  const days = span === "week" ? rangeDays(addDays(today, -6), today) : span === "month" ? rangeDays(`${today.slice(0, 8)}01`, today) : rangeDays(addDays(today, -30), today);
  const hours = (data.rows ?? []).length ? days.flatMap((day) => hoursForDay(data.rows ?? [], zone, day)) : [];
  const totals = sumHours(hours);
  const assumed = Number(rate);
  const lkr = totals && Number.isFinite(assumed) && assumed > 0 ? Math.round(totals.imported * assumed) : null;

  return (
    <Frame>
      <RequireDemo>
        <AppHeader title="Savings estimate" simulated={data.snapshot.simulated} offline={data.snapshot.mode === "offline"} action={<span className="hh-pill estimated">Estimated</span>} />
        <div className="hh-main">
          <p className="hh-fine">From forecast hours in this range. Not a bill and not a measured saving.</p>
          <Segmented
            label="Savings range"
            value={span}
            onChange={setSpan}
            options={[
              { id: "week", label: "Week" },
              { id: "month", label: "Month" },
              { id: "pilot", label: "Pilot" },
            ]}
          />
          <section className="hh-card">
            <p className="hh-fine">Forecast solar used at home</p>
            <strong style={{ fontSize: 28 }}><CountUp value={totals?.solarUsed ?? null} suffix="kWh" /></strong>
            <p className="hh-note">Usual column is blank. There is no pre-pilot measured history in this app.</p>
            <span className="hh-pill estimated">Verification pending</span>
          </section>
          <section className="hh-card">
            <table className="hh-table">
              <thead><tr><th></th><th>Forecast</th><th>Usual</th></tr></thead>
              <tbody>
                <tr><td>Import</td><td>{totals ? `${totals.imported.toFixed(1)} kWh` : "—"}</td><td>—</td></tr>
                <tr><td>Export</td><td>{totals ? `${totals.exported.toFixed(1)} kWh` : "—"}</td><td>—</td></tr>
                <tr><td>Demand</td><td>{totals ? `${totals.demand.toFixed(1)} kWh` : "—"}</td><td>—</td></tr>
              </tbody>
            </table>
          </section>
          <section className="hh-card">
            <button type="button" className="hh-choice" onClick={() => setOpen((value) => !value)}>
              <span className="hh-grow"><strong>How this is calculated</strong><span>Forecast arithmetic, not a tariff engine.</span></span>
              <span>{open ? "▴" : "▾"}</span>
            </button>
            {open ? (
              <>
                <p className="hh-note">Import is the sum of positive net (demand minus PV) on forecast hours. Export is the sum of the negative side. Household use is the demand forecast. Scheme label: {demo?.profile?.scheme ?? "not set"}.</p>
                <div className="hh-field">
                  <label htmlFor="rate">Assumed LKR per imported kWh</label>
                  <div className="hh-input"><input id="rate" inputMode="decimal" value={rate} placeholder="Leave blank" onChange={(event) => setRate(event.target.value)} /></div>
                  <p className="hh-local">Optional assumption you type. It is not your CEB bill and not a verified tariff.</p>
                </div>
                <p className="hh-note">{lkr === null ? "LKR stays hidden until you enter an assumption." : `Assumed import cost: LKR ${lkr.toLocaleString("en-LK")}. This is your rate times forecast import.`}</p>
              </>
            ) : null}
          </section>
          <div className="hh-banner warn">
            <div>
              <strong>kWh-only until verification</strong>
              <p>Site verification is pending. The headline stays in kWh.</p>
            </div>
          </div>
        </div>
      </RequireDemo>
    </Frame>
  );
}
