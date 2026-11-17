"use client";

import { useEffect, useMemo, useState } from "react";
import { ApplianceCard } from "@/components/household/appliance-card";
import { IconGrid, IconHome, IconOffline, IconSun } from "@/components/household/icons";
import { MetricCard } from "@/components/household/metric-card";
import { ExamplePill, StatusPill } from "@/components/household/pills";
import { PowerFlow } from "@/components/household/power-flow";
import { TabBar, type HouseholdTab } from "@/components/household/tab-bar";
import { TodayCard } from "@/components/household/today-card";
import { formatIssued } from "@/lib/forecast";
import type { ForecastRow } from "@/lib/forecast";
import {
  buildSnapshot,
  dominantGrid,
  formatPower,
  formatSystemKw,
  formatUpdated,
  type SiteDetail,
} from "@/lib/household";
import { browserSupabase } from "@/lib/supabase";
import "./household.css";

const HOUR_MS = 60 * 60 * 1000;

export default function HouseholdPage() {
  const supabase = useMemo(() => browserSupabase(), []);
  const [sites, setSites] = useState<SiteDetail[]>([]);
  const [siteId, setSiteId] = useState("");
  const [rows, setRows] = useState<ForecastRow[] | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<HouseholdTab>("home");

  useEffect(() => {
    if (!supabase) return;
    let stop = false;
    async function loadSites() {
      const { data, error: siteError } = await supabase!
        .from("sites")
        .select("site_id,name,timezone,system_kw")
        .order("site_id");
      if (stop) return;
      if (siteError) {
        setError(siteError.message);
        return;
      }
      const list = (data ?? []) as SiteDetail[];
      setSites(list);
      const wanted = new URLSearchParams(window.location.search).get("site");
      setSiteId((current) => {
        if (current && list.some((site) => site.site_id === current)) return current;
        if (wanted && list.some((site) => site.site_id === wanted)) return wanted;
        return list[0]?.site_id ?? "";
      });
    }
    void loadSites();
    const timer = window.setInterval(() => void loadSites(), HOUR_MS);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [supabase]);

  useEffect(() => {
    if (!supabase || !siteId) return;
    let stop = false;
    async function loadForecast() {
      const { data: latest, error: latestError } = await supabase!
        .from("forecasts")
        .select("issued_at")
        .eq("site_id", siteId)
        .order("issued_at", { ascending: false })
        .limit(1);
      if (stop) return;
      if (latestError) {
        setError(latestError.message);
        setRows([]);
        return;
      }
      const issued = latest?.[0]?.issued_at as string | undefined;
      if (!issued) {
        setRows([]);
        setError("");
        return;
      }
      const { data, error: rowError } = await supabase!
        .from("forecasts")
        .select("target,timestamp,issued_at,value_kw,baseline_kw,model_version,data_label,is_simulated")
        .eq("site_id", siteId)
        .eq("issued_at", issued)
        .order("timestamp");
      if (stop) return;
      if (rowError) {
        setError(rowError.message);
        setRows([]);
        return;
      }
      setError("");
      setRows((data ?? []) as ForecastRow[]);
    }
    void loadForecast();
    const timer = window.setInterval(() => void loadForecast(), HOUR_MS);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [supabase, siteId]);

  function chooseSite(next: string) {
    setSiteId(next);
    const url = new URL(window.location.href);
    url.searchParams.set("site", next);
    window.history.replaceState(null, "", url);
  }

  if (!supabase) {
    return (
      <main className="hh">
        <header className="hh-hdr">
          <div>
            <p className="hh-eyebrow">SOLAR USER</p>
            <h1>Household</h1>
          </div>
        </header>
        <div className="hh-main">
          <p className="hh-setup">
            Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY. Use the publishable key, not the service role key.
          </p>
        </div>
      </main>
    );
  }

  const site = sites.find((item) => item.site_id === siteId);
  const zone = site?.timezone || "Asia/Colombo";
  const forecast = rows ?? [];
  const snapshot = buildSnapshot(forecast, zone);
  const grid = dominantGrid(snapshot);
  const system = formatSystemKw(site?.system_kw ?? null);
  const title = site ? `${site.name || site.site_id}${system ? ` · ${system}` : ""}` : "Household";
  const updated = formatUpdated(snapshot.issuedAt);
  const historyHref = siteId ? `/?site=${encodeURIComponent(siteId)}` : "/";
  const offline = snapshot.mode === "offline";
  const caption = (live: string) => (offline ? "Last known" : live);

  return (
    <main className="hh">
      <header className="hh-hdr">
        <div>
          <p className="hh-eyebrow">SOLAR USER</p>
          <h1>{title}</h1>
          <a className="hh-link" href={historyHref}>
            Forecast chart
          </a>
        </div>
        <div className="hh-hdr-side">
          <StatusPill offline={offline || forecast.length === 0} />
          {snapshot.simulated ? <ExamplePill /> : null}
        </div>
      </header>
      {sites.length > 1 ? (
        <div className="hh-site">
          <label className="hh-fine" htmlFor="household-site">
            Home
          </label>
          <select id="household-site" value={siteId} onChange={(event) => chooseSite(event.target.value)}>
            {sites.map((item) => (
              <option key={item.site_id} value={item.site_id}>
                {item.name || item.site_id}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {tab === "home" ? (
        <div className="hh-main">
          {error ? <p className="hh-setup">{error}</p> : null}
          {rows === null ? <p className="hh-loading">Loading…</p> : null}
          {rows !== null ? (
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
                <MetricCard
                  icon={<IconSun size={14} stroke="#a14a07" />}
                  label="Solar now"
                  value={formatPower(snapshot.solar.value, "kW")}
                  caption={caption("Generating")}
                  source={snapshot.solar.source}
                  stale={offline}
                  updated={updated}
                />
                <MetricCard
                  icon={<IconHome size={14} stroke="#a14a07" />}
                  label="Home use"
                  value={formatPower(snapshot.home.value, "kW")}
                  caption={caption("Forecast")}
                  source={snapshot.home.source}
                  stale={offline}
                  updated={updated}
                />
                <MetricCard
                  icon={<IconGrid size={14} stroke="#0268a8" />}
                  label="Grid"
                  value={formatPower(grid.value, "kW")}
                  caption={caption(grid.caption)}
                  source={grid.source}
                  stale={offline}
                  updated={updated}
                />
              </div>
              <TodayCard
                generated={snapshot.generatedKwh}
                used={snapshot.usedKwh}
                exported={snapshot.exportedKwh}
                imported={snapshot.importedKwh}
                stale={offline}
                historyHref={historyHref}
                footnote={
                  snapshot.issuedAt
                    ? `Issued ${formatIssued(snapshot.issuedAt, zone)}`
                    : "No forecast issued"
                }
              />
              {forecast.length > 0 ? <ApplianceCard window={snapshot.window} timeZone={zone} /> : null}
            </>
          ) : null}
        </div>
      ) : (
        <div className="hh-main">
          <section className="hh-card hh-placeholder">
            <h2>{tab[0].toUpperCase() + tab.slice(1)}</h2>
            <p>This screen is not built yet. Home is the only working tab. Nothing here controls equipment.</p>
          </section>
        </div>
      )}
      <TabBar tab={tab} onChange={setTab} />
    </main>
  );
}
