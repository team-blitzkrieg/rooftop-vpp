import { formatIssued } from "@/lib/forecast";
import type { ApplianceWindow } from "@/lib/household";
import { IconSun } from "./icons";
import { SourcePill } from "./pills";

export function ApplianceCard({ window, timeZone }: { window: ApplianceWindow | null; timeZone: string }) {
  return (
    <section className="hh-card hh-appliance">
      <div className="hh-sunbox">
        <IconSun size={20} stroke="#a14a07" />
      </div>
      <div>
        <p className="hh-fine">Best time to run appliances</p>
        <strong>{window ? window.label : "—"}</strong>
        <p className="hh-fine">
          {window
            ? `From the latest forecast · Issued ${formatIssued(window.issuedAt, timeZone)}`
            : "Needs three forecast hours of PV."}
        </p>
        <div className="hh-pills">{window ? <SourcePill source={window.source} /> : <span className="hh-pill none">Not available</span>}</div>
      </div>
    </section>
  );
}
