"use client";

import { useRouter } from "next/navigation";
import { IconCheck } from "@/components/household/icons";
import { AppHeader, RequireDemo } from "@/components/household/shell";
import { Button, Modal } from "@/components/household/ui";
import { useDemo } from "@/lib/demo-store";
import { useState } from "react";
import { Stepper } from "@/components/household/stepper";

export default function ReceiptPage() {
  const router = useRouter();
  const demo = useDemo();
  const [open, setOpen] = useState(false);
  const consent = demo?.consent;
  const when = consent ? new Date(consent.agreedAt) : null;
  const id = when ? `CR-${when.getFullYear()}-${String(when.getMonth() + 1).padStart(2, "0")}${String(when.getDate()).padStart(2, "0")}` : "—";

  return (
    <main className="hh">
      <RequireDemo onboarding>
        <AppHeader title="Consent receipt" back={{ href: "/household/collect", label: "Back" }} />
        <div className="hh-main">
          <Stepper current={2} />
          <p className="hh-fine" style={{ textAlign: "center" }}>Step 2 of 3</p>
          <div style={{ textAlign: "center" }}>
            <div className="hh-iconbox" style={{ background: "#43a04722", margin: "0 auto 8px", width: 48, height: 48, borderRadius: 24 }}>
              <IconCheck size={22} stroke="#2a7130" />
            </div>
            <h2>{consent ? "You're in" : "No consent saved yet"}</h2>
            <p className="hh-note">A copy stays in this browser. Settings can show it again.</p>
          </div>
          <section className="hh-card">
            <div className="hh-row"><h2>Receipt</h2><span className="hh-pill none">{id}</span></div>
            <Row k="Consent version" v={consent?.version ?? "—"} />
            <Row k="Agreed" v={when ? when.toLocaleString("en-GB", { timeZone: "Asia/Colombo" }) : "—"} />
            <Row k="Account" v={demo?.session?.email ?? "—"} />
            <Row k="Storage" v="This browser only" />
            <p className="hh-fine">Scopes</p>
            <p className="hh-note">{consent?.scopes.solar ? "Solar output" : "Solar hidden"} · {consent?.scopes.grid ? "Grid" : "Grid hidden"} · {consent?.scopes.home ? "Household use" : "Household hidden"} · Appliance-level not available · {consent?.scopes.totals ? "Anonymised totals included" : "Anonymised totals not included"}</p>
          </section>
          <Button type="button" onClick={() => router.push("/household/profile")}>Continue</Button>
          <button type="button" className="hh-btn ghost" onClick={() => setOpen(true)}>Download receipt (PDF)</button>
        </div>
      </RequireDemo>
      <Modal open={open} title="Receipt download" onClose={() => setOpen(false)}>
        <p className="hh-note">A PDF is not generated. The receipt above is the local record. Forecasts in Supabase are unchanged.</p>
        <Button type="button" onClick={() => setOpen(false)}>Close</Button>
      </Modal>
    </main>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="hh-row" style={{ padding: "8px 0", borderBottom: "1px solid #e5e7eb" }}>
      <span className="hh-fine">{k}</span>
      <strong style={{ fontSize: 13 }}>{v}</strong>
    </div>
  );
}
