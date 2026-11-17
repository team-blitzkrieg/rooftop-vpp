"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { IconInfo } from "@/components/household/icons";
import { AppHeader, RequireDemo } from "@/components/household/shell";
import { Button } from "@/components/household/ui";
import { useDemo, updateDemo } from "@/lib/demo-store";
import { useHomeData } from "@/components/household/use-home-data";
import { Stepper } from "@/components/household/stepper";

export default function ProfilePage() {
  const router = useRouter();
  const demo = useDemo();
  const data = useHomeData();
  const [scheme, setScheme] = useState("net-metering");
  const [tariff, setTariff] = useState("Domestic label");
  const [systemKw, setSystemKw] = useState("");
  const [effective, setEffective] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!demo) return;
    setScheme(demo.profile?.scheme ?? "net-metering");
    setTariff(demo.profile?.tariffLabel ?? "Domestic label");
    setSystemKw(demo.profile?.systemKw || (data.site?.system_kw ? String(data.site.system_kw) : ""));
    setEffective(demo.profile?.effective ?? "");
  }, [demo, data.site]);

  function finish() {
    const kw = Number(systemKw);
    if (!Number.isFinite(kw) || kw <= 0) {
      setError("Enter a system size above 0 kW. It is saved on this browser only.");
      return;
    }
    setError("");
    updateDemo((state) => ({
      ...state,
      profile: { scheme: scheme as "net-metering" | "net-accounting" | "net-plus", tariffLabel: tariff, systemKw: String(kw), effective },
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
              <label htmlFor="scheme">Connection scheme</label>
              <div className="hh-input">
                <select id="scheme" className="hh-select" value={scheme} onChange={(event) => setScheme(event.target.value)} style={{ flex: 1, border: 0, background: "transparent", font: "inherit" }}>
                  <option value="net-metering">Net metering</option>
                  <option value="net-accounting">Net accounting</option>
                  <option value="net-plus">Net plus</option>
                </select>
              </div>
            </div>
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
