"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  chartPoints,
  eveningPeak,
  formatIssued,
  formatKwh,
  isSimulated,
  isStale,
  sumKwh,
  todayKey,
  type ForecastRow,
  type SiteRow,
} from "@/lib/forecast";

const HOUR_MS = 60 * 60 * 1000;

function client(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key);
}

export default function Page() {
  const supabase = useMemo(() => client(), []);
  const [sites, setSites] = useState<SiteRow[]>([]);
  const [siteId, setSiteId] = useState("");
  const [rows, setRows] = useState<ForecastRow[] | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!supabase) return;
    let stop = false;

    async function loadSites() {
      const { data, error: siteError } = await supabase!
        .from("sites")
        .select("site_id,name,timezone")
        .order("site_id");
      if (stop) return;
      if (siteError) {
        setError(siteError.message);
        setLoading(false);
        return;
      }
      const list = (data ?? []) as SiteRow[];
      setSites(list);
      setSiteId((current) => current || list[0]?.site_id || "");
      setLoading(false);
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

  if (!supabase) {
    return (
      <main className="page">
        <h1>Household forecast</h1>
        <p className="empty">
          Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY. Use the
          publishable key, not the service role key.
        </p>
      </main>
    );
  }

  const zone = sites.find((site) => site.site_id === siteId)?.timezone || "Asia/Colombo";
  const forecast = rows ?? [];
  const issuedAt = forecast[0]?.issued_at;
  const points = chartPoints(forecast, zone);
  const day = todayKey(zone);
  const pvToday = sumKwh(forecast.filter((row) => row.target === "pv"), zone, day);
  const demandToday = sumKwh(forecast.filter((row) => row.target === "demand"), zone, day);
  const peak = eveningPeak(forecast.filter((row) => row.target === "demand"), zone);

  return (
    <main className="page">
      <header className="header">
        <div>
          <p className="eyebrow">Rooftops</p>
          <h1>Household forecast</h1>
          <p className="sub">Next 48 hours. The page checks again once an hour.</p>
        </div>
        <div>
          <label htmlFor="site">Home</label>
          <select
            id="site"
            value={siteId}
            onChange={(event) => setSiteId(event.target.value)}
            disabled={sites.length === 0}
          >
            {sites.length === 0 ? <option value="">No homes yet</option> : null}
            {sites.map((site) => (
              <option key={site.site_id} value={site.site_id}>
                {site.name || site.site_id}
              </option>
            ))}
          </select>
        </div>
      </header>

      {error ? <p className="empty">{error}</p> : null}

      {loading ? <p className="empty">Loading…</p> : null}

      {!loading && forecast.length === 0 ? (
        <section className="card">
          <p className="empty">
            No forecast for this home yet. On GitHub, open Actions, choose Seed demo, and run
            the workflow.
          </p>
        </section>
      ) : null}

      {forecast.length > 0 && issuedAt ? (
        <>
          <div className="badges">
            {isSimulated(forecast) ? <span className="badge sim">SIMULATED data</span> : null}
            {isStale(issuedAt) ? <span className="badge stale">Stale</span> : null}
          </div>
          <section className="card">
            <ResponsiveContainer width="100%" height={340}>
              <LineChart data={points} margin={{ top: 12, right: 8, left: 0, bottom: 8 }}>
                <CartesianGrid stroke="#e7e5e4" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "#57534e", fontSize: 12 }} minTickGap={28} />
                <YAxis
                  tick={{ fill: "#57534e", fontSize: 12 }}
                  width={48}
                  label={{ value: "kW", angle: -90, position: "insideLeft", fill: "#57534e" }}
                />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="pv" name="PV" stroke="#1f7a4d" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="demand" name="Demand" stroke="#c05621" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="net" name="Net" stroke="#234e70" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="pvBase" name="PV baseline" stroke="#1f7a4d" dot={false} strokeOpacity={0.35} strokeDasharray="4 4" />
                <Line type="monotone" dataKey="demandBase" name="Demand baseline" stroke="#c05621" dot={false} strokeOpacity={0.35} strokeDasharray="4 4" />
                <Line type="monotone" dataKey="netBase" name="Net baseline" stroke="#234e70" dot={false} strokeOpacity={0.35} strokeDasharray="4 4" />
              </LineChart>
            </ResponsiveContainer>
          </section>
          <section className="stats">
            <article className="stat">
              <p>Today&apos;s expected PV</p>
              <strong>{formatKwh(pvToday)}</strong>
            </article>
            <article className="stat">
              <p>Today&apos;s expected demand</p>
              <strong>{formatKwh(demandToday)}</strong>
            </article>
            <article className="stat">
              <p>Evening peak</p>
              <strong>{peak ?? "—"}</strong>
            </article>
          </section>
          <p className="meta">
            model_version {forecast[0].model_version} · issued {formatIssued(issuedAt, zone)}
          </p>
        </>
      ) : null}

      <footer>Read-only. This page does not control equipment.</footer>
    </main>
  );
}
