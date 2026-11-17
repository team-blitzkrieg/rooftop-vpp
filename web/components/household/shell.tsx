"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useDemo } from "@/lib/demo-store";
import { formatSystemKw, type SiteDetail } from "@/lib/household";
import { copy } from "@/lib/copy";
import { ExamplePill, StatusPill } from "./pills";
import { TabBar } from "./tab-bar";

export function RequireDemo({ children, onboarding = false }: { children: ReactNode; onboarding?: boolean }) {
  const demo = useDemo();
  const router = useRouter();
  useEffect(() => {
    if (!demo) return;
    if (!demo.session) router.replace("/household/sign-in");
    else if (!onboarding && !demo.consent && !demo.consentSkipped) router.replace("/household/welcome");
  }, [demo, onboarding, router]);
  if (!demo?.session) return <div className="hh-main"><div className="hh-skel hh-skel-card" /></div>;
  if (!onboarding && !demo.consent && !demo.consentSkipped) return <div className="hh-main"><div className="hh-skel hh-skel-card" /></div>;
  return children;
}

export function AppHeader({
  eyebrow = "SOLAR USER",
  title,
  back,
  action,
  offline,
  simulated,
}: {
  eyebrow?: string;
  title: string;
  back?: { href: string; label: string };
  action?: ReactNode;
  offline?: boolean;
  simulated?: boolean;
}) {
  return (
    <header className="hh-hdr">
      <div>
        {back ? (
          <Link className="hh-back" href={back.href}>
            {back.label}
          </Link>
        ) : (
          <p className="hh-eyebrow">{eyebrow}</p>
        )}
        <h1>{title}</h1>
      </div>
      <div className="hh-hdr-side">
        {action}
        <span className="hh-pill example">{copy.mode}</span>
        {offline === undefined ? null : <StatusPill offline={offline} />}
        {simulated ? <ExamplePill /> : null}
      </div>
    </header>
  );
}

export function SiteTitle({ site }: { site: SiteDetail | null }) {
  if (!site) return "Household";
  const system = formatSystemKw(site.system_kw);
  return `${site.name || site.site_id}${system ? ` · ${system}` : ""}`;
}

export function SiteSelect({
  sites,
  siteId,
  onChange,
}: {
  sites: SiteDetail[];
  siteId: string;
  onChange: (id: string) => void;
}) {
  if (sites.length < 2) return null;
  return (
    <div className="hh-site">
      <label className="hh-fine" htmlFor="household-site">
        Home
      </label>
      <select id="household-site" value={siteId} onChange={(event) => onChange(event.target.value)}>
        {sites.map((site) => (
          <option key={site.site_id} value={site.site_id}>
            {site.name || site.site_id}
          </option>
        ))}
      </select>
    </div>
  );
}

export function Frame({ children }: { children: ReactNode }) {
  return (
    <main className="hh">
      <div className="hh-page">{children}</div>
      <TabBar />
    </main>
  );
}
