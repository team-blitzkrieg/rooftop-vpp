"use client";

import { useEffect, useState } from "react";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { CountUp, Segmented } from "@/components/household/ui";
import { useHomeData } from "@/components/household/use-home-data";
import { useDemo } from "@/lib/demo-store";
import { addDays, hoursForDay, rangeDays, sumHours, todayKey } from "@/lib/household-derive";
import { feedInLkr, schemeLabel, schemeWhy, type Scheme } from "@/lib/scheme-rules";

export default function SavingsPage() {
  const data = useHomeData();
  const demo = useDemo();
  const zone = data.zone;
  const today = todayKey(zone);
  const [span, setSpan] = useState<"week" | "month" | "pilot">("month");
  const [open, setOpen] = useState(false);
  const [rate, setRate] = useState("");
  const [serverNote, setServerNote] = useState("");
  const scheme: Scheme = demo?.profile?.scheme ?? "net-plus";
  const systemKw = Number(demo?.profile?.systemKw || data.site?.system_kw || 0);
  useEffect(() => {
    if (!data.siteId) return;
    const params = new URLSearchParams({
      site: data.siteId,
      scheme,
      system_kw: String(systemKw || data.site?.system_kw || 3),
    });
    let stop = false;
    void fetch(`/api/household/savings?${params}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (stop || !body) return;
        const money = body.lkr == null ? `${body.kwh} kWh` : `LKR ${body.lkr} from ${body.kwh} kWh`;
        setServerNote(`Server figure: ${money}. ${body.data_label}. ${body.note}`);
      })
      .catch(() => undefined);
    return () => {
      stop = true;
    };
  }, [data.siteId, data.site?.system_kw, scheme, systemKw]);
  const days = span === "week" ? rangeDays(addDays(today, -6), today) : span === "month" ? rangeDays(`${today.slice(0, 8)}01`, today) : rangeDays(addDays(today, -30), today);
  const hours = (data.rows ?? []).length ? days.flatMap((day) => hoursForDay(data.rows ?? [], zone, day)) : [];
  const totals = sumHours(hours);
  const fit = feedInLkr(systemKw > 0 ? systemKw : 5);
  const assumed = Number(rate);
  const generated = totals?.pv == null ? null : Math.round(totals.pv * 10) / 10;
  const usedAtHome = totals?.solarUsed == null ? null : Math.round(totals.solarUsed * 10) / 10;
  const netPlusIncome = generated === null ? null : Math.round(generated * fit);
  const accounting = usedAtHome !== null && Number.isFinite(assumed) && assumed > fit
    ? Math.round(usedAtHome * (assumed - fit))
    : null;

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
          <p className="hh-note">{schemeLabel(scheme)}. {schemeWhy(scheme)} {demo?.profile ? "" : "No scheme is saved yet, so this uses the Net Plus version."}</p>
          {serverNote ? <p className="hh-fine">{serverNote}</p> : null}
          <section className="hh-card">
            {scheme === "net-plus" ? (
              <>
                <p className="hh-fine">Forecast export income</p>
                <strong style={{ fontSize: 28 }}>{netPlusIncome === null ? "—" : `LKR ${netPlusIncome.toLocaleString("en-LK")}`}</strong>
                <p className="hh-note">{generated === null ? "No PV forecast in this range." : `${generated.toFixed(1)} kWh × LKR ${fit} (feed-in for this system size). Not a payment advice.`}</p>
                <p className="hh-note">Income at risk from faults is not measured here. The settings check has not read an inverter.</p>
              </>
            ) : null}
            {scheme === "net-metering" ? (
              <>
                <p className="hh-fine">Forecast solar used at home</p>
                <strong style={{ fontSize: 28 }}><CountUp value={usedAtHome} suffix="kWh" /></strong>
                <p className="hh-note">No rupee saving is shown. Banked export changes with timing, and this app does not turn that into a bill.</p>
              </>
            ) : null}
            {scheme === "net-accounting" ? (
              <>
                <p className="hh-fine">Forecast solar used at home</p>
                <strong style={{ fontSize: 28 }}><CountUp value={usedAtHome} suffix="kWh" /></strong>
                <p className="hh-note">{accounting === null ? "Enter a buy rate below to see an assumed rupee difference after lost export income." : `Assumed difference LKR ${accounting.toLocaleString("en-LK")}: your buy rate minus LKR ${fit} feed-in, times solar used at home.`}</p>
              </>
            ) : null}
            <span className="hh-pill estimated">Forecast × published rate</span>
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
                <p className="hh-note">Import, export and demand are sums of forecast hours. Usual is blank because there is no measured pre-pilot history. Feed-in used here is LKR {fit} per kWh for a {systemKw || "—"} kW system.</p>
                {scheme === "net-accounting" ? (
                  <div className="hh-field">
                    <label htmlFor="rate">Assumed buy rate, LKR per kWh</label>
                    <div className="hh-input"><input id="rate" inputMode="decimal" value={rate} placeholder="Leave blank" onChange={(event) => setRate(event.target.value)} /></div>
                    <p className="hh-local">You type this. It is not a CEB slab. The difference subtracts LKR {fit} of export income given up.</p>
                  </div>
                ) : <p className="hh-note">This scheme does not turn a typed buy rate into a saving.</p>}
              </>
            ) : null}
          </section>
          <div className="hh-banner warn">
            <div>
              <strong>{scheme === "net-metering" ? "kWh only for Net Metering" : "Verification pending"}</strong>
              <p>{scheme === "net-plus" ? "The rupee line is forecast kWh times the published feed-in rate. It is not money shifted by the plan." : "Site verification is pending. Nothing here is a CEB bill."}</p>
            </div>
          </div>
        </div>
      </RequireDemo>
    </Frame>
  );
}
