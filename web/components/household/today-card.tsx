import type { Quantity } from "@/lib/household";
import { SourcePill } from "./pills";
import { CountUp } from "./ui";

function Cell({ dot, label, quantity, unit }: { dot: string; label: string; quantity: Quantity; unit: "kWh" }) {
  return (
    <div className="hh-today-cell">
      <p>
        <i className={`hh-swatch ${dot}`} />
        {label}
      </p>
      <strong><CountUp value={quantity.value} suffix={unit} /></strong>
    </div>
  );
}

export function TodayCard({
  generated,
  used,
  exported,
  imported,
  stale,
  historyHref,
  footnote,
}: {
  generated: Quantity;
  used: Quantity;
  exported: Quantity;
  imported: Quantity;
  stale: boolean;
  historyHref: string;
  footnote: string;
}) {
  const sources = [generated.source, used.source, exported.source, imported.source].filter(
    (source): source is NonNullable<typeof source> => source !== null,
  );
  const unique = sources.filter((source, index) => sources.findIndex((item) => item.kind === source.kind) === index);

  return (
    <section className="hh-card">
      <div className="hh-row">
        <h2>Today</h2>
        <a className="hh-link" href={historyHref}>
          View history
        </a>
      </div>
      <div className="hh-today">
        <Cell dot="solar" label="Generated" quantity={generated} unit="kWh" />
        <Cell dot="used" label="Used" quantity={used} unit="kWh" />
        <Cell dot="export" label="Exported" quantity={exported} unit="kWh" />
        <Cell dot="import" label="Imported" quantity={imported} unit="kWh" />
      </div>
      <div className="hh-row hh-today-foot">
        <div className="hh-pills">
          {stale ? <span className="hh-pill stale">Stale</span> : null}
          {unique.length === 0 ? <span className="hh-pill none">Not available</span> : unique.map((source) => <SourcePill key={source.kind} source={source} />)}
        </div>
        <p className="hh-fine">{footnote}</p>
      </div>
    </section>
  );
}
