"use client";

import Link from "next/link";
import { ApplianceCard } from "@/components/household/appliance-card";
import { IconGrid, IconHome, IconOffline, IconSun } from "@/components/household/icons";
import { MetricCard } from "@/components/household/metric-card";
import { PowerFlow } from "@/components/household/power-flow";
import { AppHeader, Frame, RequireDemo, SiteSelect, SiteTitle } from "@/components/household/shell";
import { TodayCard } from "@/components/household/today-card";
import { useHomeData } from "@/components/household/use-home-data";
import { formatIssued } from "@/lib/forecast";
import { dominantGrid, formatPower, formatUpdated } from "@/lib/household";

export default function HouseholdPage() {
  const data = useHomeData();
  if (data.supabaseMissing) {
    return (
      <main className="hh">
        <AppHeader title="Household" />
        <div className="hh-main">
          <p className="hh-setup">
            Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY. Use the publishable key, not the service role key.
          </p>
        </div>
      </main>
    );
  }

  const forecast = data.rows ?? [];
  const snapshot = data.snapshot;
  const grid = dominantGrid(snapshot);
  const offline = snapshot.mode === "offline";
  const updated = formatUpdated(snapshot.issuedAt);
  const historyHref = `/household/history?site=${encodeURIComponent(data.siteId)}`;
  const caption = (live: string) => (offline ? "Last known" : live);

  return (
    <Frame>
      <RequireDemo>
        <AppHeader
          title={SiteTitle({ site: data.site })}
          offline={offline || forecast.length === 0}
          simulated={snapshot.simulated}
        />
        <div className="hh-main" style={{ paddingTop: 0 }}>
          <Link className="hh-link" href={data.siteId ? `/?site=${encodeURIComponent(data.siteId)}` : "/"}>
            Forecast chart
          </Link>
        </div>
        <SiteSelect sites={data.sites} siteId={data.siteId} onChange={data.chooseSite} />
        <div className="hh-main">
          {data.error ? <p className="hh-setup">{data.error}</p> : null}
          {data.rows === null ? <div className="hh-skel hh-skel-card" /> : null}
          {data.rows !== null ? (
            <>
              {snapshot.bannerTitle ? (
                <div className="hh-banner">
                  <IconOffline size={18} stroke="#b71c1c" />
                  <div>
                    <strong>{snapshot.bannerTitle}</strong>
                    <p>{snapshot.bannerBody}</p>
                  </div>
                </div>
              ) : null}
              <PowerFlow snapshot={snapshot} updated={updated} />
              <div className="hh-metrics">
                <MetricCard icon={<IconSun size={14} stroke="#a14a07" />} label="Solar now" value={formatPower(snapshot.solar.value, "kW")} caption={caption("Generating")} source={snapshot.solar.source} stale={offline} updated={updated} />
                <MetricCard icon={<IconHome size={14} stroke="#a14a07" />} label="Home use" value={formatPower(snapshot.home.value, "kW")} caption={caption("Forecast")} source={snapshot.home.source} stale={offline} updated={updated} />
                <MetricCard icon={<IconGrid size={14} stroke="#0268a8" />} label="Grid" value={formatPower(grid.value, "kW")} caption={caption(grid.caption)} source={grid.source} stale={offline} updated={updated} />
              </div>
              <TodayCard
                generated={snapshot.generatedKwh}
                used={snapshot.usedKwh}
                exported={snapshot.exportedKwh}
                imported={snapshot.importedKwh}
                stale={offline}
                historyHref={historyHref}
                footnote={snapshot.issuedAt ? `Issued ${formatIssued(snapshot.issuedAt, data.zone)}` : "No forecast issued"}
              />
              {forecast.length > 0 ? (
                <Link href="/household/forecast" className="hh-plain">
                  <ApplianceCard window={snapshot.window} timeZone={data.zone} />
                </Link>
              ) : null}
            </>
          ) : null}
        </div>
      </RequireDemo>
    </Frame>
  );
}
