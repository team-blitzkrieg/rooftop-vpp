import { formatPower, type HouseholdSnapshot, type SourceBadge } from "@/lib/household";
import { IconBattery, IconGrid, IconHome, IconLeaf, IconSun } from "./icons";
import { SourcePill } from "./pills";

export function PowerFlow({
  snapshot,
  updated,
}: {
  snapshot: HouseholdSnapshot;
  updated: string;
}) {
  const offline = snapshot.mode === "offline";
  const solar = formatPower(snapshot.solar.value, "kW");
  const home = formatPower(snapshot.home.value, "kW");
  const incoming = formatPower(snapshot.importing.value, "kW");
  const outgoing = formatPower(snapshot.exporting.value, "kW");
  const share =
    snapshot.selfPoweredPct === null ? "—" : `${Math.round(snapshot.selfPoweredPct)}%`;

  return (
    <section className="hh-card">
      <div className="hh-row">
        <h2>Power flow</h2>
        <p className="hh-muted">Forecast · kW</p>
      </div>
      <div className={`hh-flow ${offline ? "off" : ""}`}>
        <svg className="hh-flow-lines" viewBox="0 0 296 312" fill="none" aria-hidden="true">
          <path d="M148 96V220" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 4" fill="none" />
          <path d="M76 166H220" stroke="#488fc2" strokeOpacity="0.4" strokeWidth="1.5" fill="none" />
          <path d="M40 96V122" stroke="#0f9d58" strokeWidth="1.5" fill="none" />
          <path d="M156 96V128Q156 152 180 152H220" stroke="#ff9800" strokeWidth="1.5" fill="none" />
          <path d="M140 96V128Q140 152 116 152H76" stroke="#a280db" strokeWidth="1.5" fill="none" />
          <circle cx="196" cy="152" r="4" fill="#ff9800" />
          <circle cx="98" cy="152" r="4" fill="#a280db" />
          <circle cx="156" cy="114" r="3" fill="#ff9800" />
          <circle cx="40" cy="109" r="3" fill="#0f9d58" />
        </svg>
        <span className="hh-flow-label nf">Non-fossil</span>
        <span className="hh-flow-label sol">Solar</span>
        <span className="hh-flow-label gr">Grid</span>
        <span className="hh-flow-label hm">Home</span>
        <span className="hh-flow-label bat">Battery</span>
        <div className="hh-node nf">
          <IconLeaf size={16} />
          <strong>—</strong>
        </div>
        <div className="hh-node sol">
          <IconSun size={16} />
          <strong>{solar}</strong>
        </div>
        <div className="hh-node gr">
          <IconGrid size={14} />
          <strong>← {incoming}</strong>
          <strong>→ {outgoing}</strong>
        </div>
        <div className="hh-node hm">
          <IconHome size={16} />
          <strong>{home}</strong>
        </div>
        <div className="hh-node bat">
          <IconBattery size={16} />
          <strong>Not installed</strong>
        </div>
        <div className={`hh-share ${share === "—" ? "empty" : ""}`}>
          <span>Self-powered</span>
          <strong>{share}</strong>
        </div>
      </div>
      <div className="hh-row">
        <div className="hh-pills">
          {offline ? <span className="hh-pill stale">Stale</span> : null}
          <FlowSources snapshot={snapshot} />
        </div>
        <p className="hh-fine">{updated}</p>
      </div>
      <p className="hh-note">
        Non-fossil share is not in the forecast. Battery is not installed. Read-only: this app never controls your devices.
      </p>
    </section>
  );
}

function FlowSources({ snapshot }: { snapshot: HouseholdSnapshot }) {
  const sources = [snapshot.solar.source, snapshot.home.source, snapshot.importing.source].filter(
    (source): source is SourceBadge => source !== null,
  );
  const unique = sources.filter((source, index) => sources.findIndex((item) => item.text === source.text) === index);
  if (unique.length === 0) return <span className="hh-pill none">Not available</span>;
  return (
    <>
      {unique.map((source) => (
        <SourcePill key={source.text} source={source} />
      ))}
    </>
  );
}
