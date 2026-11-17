"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconAlerts, IconHome, IconPlan, IconSavings, IconSettings } from "./icons";

const TABS = [
  { href: "/household", label: "Home", icon: IconHome },
  { href: "/household/plan", label: "Plan", icon: IconPlan },
  { href: "/household/savings", label: "Savings", icon: IconSavings },
  { href: "/household/alerts", label: "Alerts", icon: IconAlerts },
  { href: "/household/settings", label: "Settings", icon: IconSettings },
] as const;

export function TabBar() {
  const path = usePathname();
  return (
    <nav className="hh-tabs" aria-label="Sections">
      {TABS.map((item) => {
        const Icon = item.icon;
        const active = item.href === "/household" ? path === "/household" : path.startsWith(item.href);
        return (
          <Link key={item.href} href={item.href} className={active ? "on" : ""} aria-current={active ? "page" : undefined}>
            <Icon />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
