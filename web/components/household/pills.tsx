import type { SourceBadge } from "@/lib/household";

export function SourcePill({ source }: { source: SourceBadge | null }) {
  if (!source) return <span className="hh-pill none">Not available</span>;
  return <span className={`hh-pill ${source.kind}`}>{source.text}</span>;
}

export function StatusPill({ offline }: { offline: boolean }) {
  return (
    <span className={`hh-status ${offline ? "off" : "on"}`}>
      <span className="hh-dot" />
      {offline ? "Offline" : "Online"}
    </span>
  );
}

export function ExamplePill() {
  return <span className="hh-pill example">Example data</span>;
}
