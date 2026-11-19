"use client";

import { useEffect, useMemo, useState } from "react";
import type { ForecastRow } from "@/lib/forecast";
import { buildSnapshot, DEMO_SIM_SITE, type SiteDetail } from "@/lib/household";
import { browserSupabase } from "@/lib/supabase";

const HOUR_MS = 60 * 60 * 1000;
const READING_MS = 5 * 60 * 1000;

export type MeterReading = {
  timestamp: string;
  pv_kw: number | null;
  consumption_kw: number | null;
  import_kw: number | null;
  export_kw: number | null;
  data_label: string;
  is_simulated: boolean;
};

export function useHomeData() {
  const supabase = useMemo(() => browserSupabase(), []);
  const [sites, setSites] = useState<SiteDetail[]>([]);
  const [siteId, setSiteId] = useState("");
  const [rows, setRows] = useState<ForecastRow[] | null>(null);
  const [readings, setReadings] = useState<MeterReading[] | null>(null);
  const [readingsNote, setReadingsNote] = useState("");
  const [error, setError] = useState("");

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
      try {
        const response = await fetch(`/api/household/forecast?site=${encodeURIComponent(siteId)}`);
        if (response.ok) {
          const body = (await response.json()) as { rows?: ForecastRow[] };
          if (stop) return;
          setError("");
          setRows(body.rows ?? []);
          return;
        }
      } catch {
        // The public table read below is the fallback.
      }
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

  useEffect(() => {
    if (siteId !== DEMO_SIM_SITE) {
      setReadings(null);
      setReadingsNote("");
      return;
    }
    let stop = false;
    async function loadReadings() {
      try {
        const response = await fetch(`/api/household/readings?site=${encodeURIComponent(siteId)}`);
        if (!response.ok) {
          if (stop) return;
          setReadings([]);
          setReadingsNote(response.status === 503 ? "The server cannot read these readings yet." : "");
          return;
        }
        const body = (await response.json()) as { rows?: MeterReading[] };
        if (!stop) {
          setReadingsNote("");
          setReadings(body.rows ?? []);
        }
      } catch {
        if (!stop) setReadings([]);
      }
    }
    void loadReadings();
    const timer = window.setInterval(() => void loadReadings(), READING_MS);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [siteId]);

  function chooseSite(next: string) {
    setSiteId(next);
    setRows(null);
    setReadings(null);
    const url = new URL(window.location.href);
    url.searchParams.set("site", next);
    window.history.replaceState(null, "", url);
  }

  const site = sites.find((item) => item.site_id === siteId) ?? null;
  const zone = site?.timezone || "Asia/Colombo";
  const snapshot = buildSnapshot(rows ?? [], zone);

  return {
    supabaseMissing: !supabase,
    sites,
    site,
    siteId,
    chooseSite,
    rows,
    readings,
    readingsNote,
    error,
    zone,
    snapshot,
  };
}
