"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { IconCheck, IconInfo } from "@/components/household/icons";
import { AppHeader, RequireDemo } from "@/components/household/shell";
import { Stepper } from "@/components/household/stepper";
import { Button } from "@/components/household/ui";
import { updateDemo, type ConsentScopes } from "@/lib/demo-store";

export default function CollectPage() {
  const router = useRouter();
  const [scopes, setScopes] = useState<ConsentScopes>({ solar: true, grid: true, home: true, appliance: false, totals: true });
  const [note, setNote] = useState("");

  function toggle(key: keyof ConsentScopes) {
    if (key === "appliance") return;
    setScopes((current) => ({ ...current, [key]: !current[key] }));
  }

  function accept() {
    if (!scopes.solar || !scopes.grid || !scopes.home) {
      setNote("Solar, grid and household use stay on. Those are the forecast fields this pilot can show.");
      return;
    }
    updateDemo((state) => ({
      ...state,
      consentSkipped: false,
      consent: { version: "v1", agreedAt: new Date().toISOString(), scopes },
    }));
    router.push("/household/receipt");
  }

  function skip() {
    updateDemo((state) => ({ ...state, consentSkipped: true }));
    router.push("/household");
  }

  return (
    <main className="hh">
      <RequireDemo onboarding>
        <AppHeader title="What we collect" back={{ href: "/household/welcome", label: "Back" }} />
        <div className="hh-main">
          <Stepper current={1} />
          <p className="hh-fine" style={{ textAlign: "center" }}>Step 1 of 3</p>
          <section className="hh-card">
            <h2>Choose what the forecast may show</h2>
            <Scope on={scopes.solar} label="Solar output" detail="Hourly PV from the forecast" tag="Forecast" onClick={() => toggle("solar")} />
            <Scope on={scopes.grid} label="Grid import and export" detail="Derived from forecast net (demand minus PV)" tag="Forecast" onClick={() => toggle("grid")} />
            <Scope on={scopes.home} label="Household use" detail="Hourly demand from the forecast" tag="Forecast" onClick={() => toggle("home")} />
            <Scope on={false} label="Appliance-level use" detail="This forecast has no per-appliance series" tag="Not available" disabled />
            <Scope on={scopes.totals} label="Anonymised pilot totals" detail="Kept after you leave, with no name attached. Stored on this browser only until a reviewed policy exists." tag="Optional" onClick={() => toggle("totals")} />
          </section>
          <div className="hh-banner info">
            <IconInfo size={16} stroke="#0268a8" />
            <p>Readings are not available with the public key. Consent here is stored on this browser only.</p>
          </div>
          {note ? <p className="hh-help">{note}</p> : null}
          <p className="hh-note">No camera, microphone or location. Raw forecast detail is described as 90 days, with hourly totals kept until the pilot ends. This is the pilot plan, not a legal opinion. Required scopes stay selected.</p>
          <div className="hh-actions">
            <Button type="button" variant="secondary" onClick={skip}>Not now</Button>
            <Button type="button" onClick={accept}>Accept and continue</Button>
          </div>
        </div>
      </RequireDemo>
    </main>
  );
}

function Scope({ on, label, detail, tag, onClick, disabled }: { on: boolean; label: string; detail: string; tag: string; onClick?: () => void; disabled?: boolean }) {
  return (
    <button type="button" className="hh-choice" onClick={onClick} disabled={disabled} aria-pressed={on}>
      <span className={`hh-check ${on ? "on" : ""}`}>{on ? <IconCheck size={12} stroke="#fff" /> : null}</span>
      <span className="hh-grow">
        <strong>{label}</strong>
        <span>{detail}</span>
      </span>
      <span className={`hh-pill ${tag === "Not available" || tag === "Optional" ? "none" : "estimated"}`}>{tag}</span>
    </button>
  );
}
