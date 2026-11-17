import type { ReactNode } from "react";
import type { SourceBadge } from "@/lib/household";
import { SourcePill } from "./pills";

export function MetricCard({
  icon,
  label,
  value,
  caption,
  source,
  stale,
  updated,
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  caption: string;
  source: SourceBadge | null;
  stale: boolean;
  updated: string;
}) {
  return (
    <article className="hh-metric">
      <div className="hh-metric-label">
        {icon}
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
      <p>{caption}</p>
      <div className="hh-pills">
        {stale ? <span className="hh-pill stale">Stale</span> : null}
        <SourcePill source={source} />
      </div>
      <p className="hh-fine">{updated}</p>
    </article>
  );
}
