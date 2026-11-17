import { IconAlerts, IconHome, IconPlan, IconSavings, IconSettings } from "./icons";

const TABS = [
  { id: "home", label: "Home", icon: IconHome },
  { id: "plan", label: "Plan", icon: IconPlan },
  { id: "savings", label: "Savings", icon: IconSavings },
  { id: "alerts", label: "Alerts", icon: IconAlerts },
  { id: "settings", label: "Settings", icon: IconSettings },
] as const;

export type HouseholdTab = (typeof TABS)[number]["id"];

export function TabBar({ tab, onChange }: { tab: HouseholdTab; onChange: (tab: HouseholdTab) => void }) {
  return (
    <nav className="hh-tabs" aria-label="Sections">
      {TABS.map((item) => {
        const Icon = item.icon;
        const active = tab === item.id;
        return (
          <button key={item.id} type="button" className={active ? "on" : ""} aria-current={active ? "page" : undefined} onClick={() => onChange(item.id)}>
            <Icon />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
