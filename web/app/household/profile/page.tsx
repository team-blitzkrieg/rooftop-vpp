"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { IconInfo } from "@/components/household/icons";
import { AppHeader, RequireDemo } from "@/components/household/shell";
import { Button } from "@/components/household/ui";
import { useDemo, updateDemo } from "@/lib/demo-store";
import { useHomeData } from "@/components/household/use-home-data";
import { Stepper } from "@/components/household/stepper";
import { FEED_IN_LKR, RATES_EFFECTIVE, RATES_REPORTED_VALID_TO, ratesWithin30Days, SCHEME_RULE_DATE, type ConnectionKind, type Scheme } from "@/lib/scheme-rules";

export default function ProfilePage() {
  const router = useRouter();
  const demo = useDemo();
  const data = useHomeData();
  const [connection, setConnection] = useState<ConnectionKind>("new");
  const [scheme, setScheme] = useState<Scheme>("net-plus");
  const [tariff, setTariff] = useState("Domestic label");
  const [systemKw, setSystemKw] = useState("");
  const [effective, setEffective] = useState("");
  const [agreementEnds, setAgreementEnds] = useState("");
  const [touMeter, setTouMeter] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!demo) return;
    const nextConnection = demo.profile?.connection ?? "new";
    setConnection(nextConnection);
    setScheme(nextConnection === "new" ? "net-plus" : demo.profile?.scheme ?? "net-plus");
    setTariff(demo.profile?.tariffLabel ?? "Domestic label");
    setSystemKw(demo.profile?.systemKw || (data.site?.system_kw ? String(data.site.system_kw) : ""));
    setEffective(demo.profile?.effective ?? "");
    setAgreementEnds(demo.profile?.agreementEnds ?? "");
    setTouMeter(demo.profile?.touMeter ?? false);
  }, [demo, data.site]);

  function finish() {
    const kw = Number(systemKw);
    if (!Number.isFinite(kw) || kw <= 0) {
      setError("Enter a system size above 0 kW. It is saved on this browser only.");
      return;
    }
    if (connection === "existing" && scheme !== "net-plus" && !agreementEnds) {
      setError("An existing Net Metering or Net Accounting agreement needs an end date.");
      return;
    }
    setError("");
    const savedScheme: Scheme = connection === "new" ? "net-plus" : scheme;
    updateDemo((state) => ({
      ...state,
      profile: {
        connection,
        scheme: savedScheme,
        tariffLabel: tariff,
        systemKw: String(kw),
        effective,
        agreementEnds,
        touMeter,
      },
    }));
    router.push("/household");
  }

  return (
    <main className="hh">
      <RequireDemo onboarding>
        <AppHeader title="Site profile" back={{ href: "/household/receipt", label: "Back" }} />
        <div className="hh-main">
          <Stepper current={3} />
          <p className="hh-fine" style={{ textAlign: "center" }}>Step 3 of 3</p>
          <section className="hh-card">
            <div className="hh-row">
              <h2>Your solar connection</h2>
              <span className="hh-pill estimated">Pending</span>
            </div>
            <div className="hh-field">
              <label htmlFor="connection">Connection</label>
              <div className="hh-input">
                <select id="connection" value={connection} onChange={(event) => {
                  const next = event.target.value as ConnectionKind;
                  setConnection(next);
                  if (next === "new") setScheme("net-plus");
                }} style={{ flex: 1, border: 0, background: "transparent", font: "inherit" }}>
                  <option value="new">New site</option>
                  <option value="existing">Existing agreement</option>
                </select>
              </div>
              <p className="hh-local">Rules changed {SCHEME_RULE_DATE}. New sites can only be Net Plus. Net Metering and Net Accounting stay available for an existing agreement.</p>
            </div>
            <div className="hh-field">
              <label htmlFor="scheme">Connection scheme</label>
              <div className="hh-input">
                <select id="scheme" className="hh-select" value={connection === "new" ? "net-plus" : scheme} disabled={connection === "new"} onChange={(event) => setScheme(event.target.value as Scheme)} style={{ flex: 1, border: 0, background: "transparent", font: "inherit" }}>
                  <option value="net-plus">Net Plus</option>
                  {connection === "existing" ? <option value="net-metering">Net Metering (existing agreement)</option> : null}
                  {connection === "existing" ? <option value="net-accounting">Net Accounting (existing agreement)</option> : null}
                </select>
              </div>
            </div>
            {connection === "existing" ? (
              <div className="hh-field">
                <label htmlFor="ends">Agreement end date</label>
                <div className="hh-input"><input id="ends" type="date" value={agreementEnds} onChange={(event) => setAgreementEnds(event.target.value)} /></div>
              </div>
            ) : null}
            <div className="hh-row">
              <div><strong>Time-of-use meter</strong><p className="hh-fine">Tick only if the utility installed one. No time-of-use prices are stored.</p></div>
              <button type="button" className={`hh-toggle ${touMeter ? "on" : ""}`} aria-pressed={touMeter} onClick={() => setTouMeter((value) => !value)}><i /></button>
            </div>
            <p className="hh-note">Feed-in rates took effect {RATES_EFFECTIVE}. Up to 10 kW: LKR {FEED_IN_LKR[0].lkrPerKwh}. Reported as valid to {RATES_REPORTED_VALID_TO}, until the next revision. This is not your bill.</p>
            {ratesWithin30Days() ? (
              <div className="hh-banner warn"><div><strong>Feed-in rates are inside 30 days of the reported end date</strong><p>Valid to {RATES_REPORTED_VALID_TO}. Treat rupee figures as provisional.</p></div></div>
            ) : null}
            <div className="hh-field">
              <label htmlFor="tariff">Tariff label</label>
              <div className="hh-input">
                <input id="tariff" value={tariff} onChange={(event) => setTariff(event.target.value)} />
              </div>
              <p className="hh-local">A label only. It is not a verified CEB tariff.</p>
            </div>
            <div className="hh-split">
              <div className="hh-field">
                <label htmlFor="kw">System size</label>
                <div className="hh-input">
                  <input id="kw" inputMode="decimal" value={systemKw} onChange={(event) => setSystemKw(event.target.value)} />
                  <span className="hh-fine">kW</span>
                </div>
              </div>
              <div className="hh-field">
                <label htmlFor="date">Effective date</label>
                <div className="hh-input">
                  <input id="date" type="date" value={effective} onChange={(event) => setEffective(event.target.value)} />
                </div>
              </div>
            </div>
          </section>
          <div className="hh-banner warn">
            <IconInfo size={16} stroke="#a14a07" />
            <div>
              <strong>Verification pending</strong>
              <p>No installer confirmation is stored. Savings stay in kWh until that exists.</p>
            </div>
          </div>
          {error ? <p className="hh-help">{error}</p> : null}
          <Button type="button" onClick={finish}>Finish setup</Button>
        </div>
      </RequireDemo>
    </main>
  );
}
