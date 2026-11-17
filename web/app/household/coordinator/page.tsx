"use client";

import { AppHeader, Frame } from "@/components/household/shell";
import { useHomeData } from "@/components/household/use-home-data";
import { useEffect, useState } from "react";
import { browserSupabase } from "@/lib/supabase";
import { useDemo } from "@/lib/demo-store";

type Assignment = { site_id: string; coordinator_id: string | null; note: string | null };
type OpenCase = { case_id: number; site_id: string; title: string; status: string };

export default function CoordinatorPage() {
  const data = useHomeData();
  const demo = useDemo();
  const [assignments, setAssignments] = useState<Assignment[] | null>(null);
  const [cases, setCases] = useState<OpenCase[]>([]);
  const [source, setSource] = useState("signed-out");
  useEffect(() => {
    let stop = false;
    void (async () => {
      const supabase = browserSupabase();
      const token = supabase ? (await supabase.auth.getSession()).data.session?.access_token : undefined;
      const response = await fetch("/api/household/coordinator", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok || stop) return;
      const body = await response.json();
      if (stop) return;
      setAssignments(body.assignments ?? []);
      setCases(body.cases ?? []);
      setSource(body.source ?? "signed-out");
    })();
    return () => {
      stop = true;
    };
  }, []);
  const assigned = new Map((assignments ?? []).map((row) => [row.site_id, row]));
  return (
    <Frame>
      <AppHeader title="Sites" back={{ href: "/household/settings", label: "‹" }} simulated={data.snapshot.simulated} />
      <div className="hh-main">
        <p className="hh-note">
          {source === "database"
            ? "Assignments and open cases are from the database."
            : "Sign in with an email code to read assignments. Demo mode does not have a coordinator record."}
        </p>
        <section className="hh-card">
          <h2>Homes</h2>
          {data.sites.length === 0 ? <p className="hh-note">No sites returned.</p> : data.sites.map((site) => {
            const row = assigned.get(site.site_id);
            const open = cases.filter((item) => item.site_id === site.site_id);
            return (
              <div key={site.site_id} className="hh-choice">
                <span className="hh-grow">
                  <strong>{site.name || site.site_id}</strong>
                  <span>
                    {row?.coordinator_id ? "Assigned" : "Unassigned"}
                    {row?.note ? ` · ${row.note}` : ""}
                    {" · "}
                    {open.length ? `${open.length} open case` : "no open case"}
                    {" · "}
                    {site.site_id === data.siteId && demo?.consent ? "consent on this account" : "no consent on this screen"}
                  </span>
                </span>
              </div>
            );
          })}
        </section>
      </div>
    </Frame>
  );
}
