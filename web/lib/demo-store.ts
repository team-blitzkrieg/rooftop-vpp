"use client";

import { useEffect, useState } from "react";

const KEY = "rooftop-household-demo";
const EVENT = "rooftop-demo";

export type Load = {
  id: string;
  name: string;
  watts: number;
  minutes: number;
  earliest: string;
  deadline: string;
  interruptible: boolean;
  manualOnly: boolean;
};

export type ConsentScopes = {
  solar: boolean;
  grid: boolean;
  home: boolean;
  appliance: boolean;
  totals: boolean;
};

export type DemoState = {
  session: { email: string; signedInAt: string; mode: "demo" | "auth"; userId: string | null } | null;
  consentSkipped: boolean;
  consent: { version: string; agreedAt: string; scopes: ConsentScopes } | null;
  profile: {
    connection: "new" | "existing";
    scheme: "net-metering" | "net-accounting" | "net-plus";
    tariffLabel: string;
    systemKw: string;
    effective: string;
    agreementEnds: string;
    touMeter: boolean;
  } | null;
  notifyAlerts: boolean;
  loads: Load[];
  paused: boolean;
  pausedAt: string | null;
  skipDay: string | null;
  seenAlerts: string[];
  withdrawReceipt: {
    id: string;
    email: string;
    at: string;
    deleteBy: string;
  } | null;
};

export const EMPTY: DemoState = {
  session: null,
  consentSkipped: false,
  consent: null,
  profile: null,
  loads: [],
  notifyAlerts: true,
  paused: false,
  pausedAt: null,
  skipDay: null,
  seenAlerts: [],
  withdrawReceipt: null,
};

export function loadDemo(): DemoState {
  if (typeof window === "undefined") return EMPTY;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return EMPTY;
    const parsed = { ...EMPTY, ...JSON.parse(raw) } as DemoState;
    if (parsed.session && !parsed.session.mode) {
      parsed.session = { ...parsed.session, mode: "demo", userId: null };
    }
    return parsed;
  } catch {
    return EMPTY;
  }
}

export function saveDemo(state: DemoState, options?: { remote?: boolean }) {
  window.localStorage.setItem(KEY, JSON.stringify(state));
  window.dispatchEvent(new Event(EVENT));
  if (!options?.remote && state.session?.mode === "auth" && state.session.userId) {
    void import("@/lib/account").then((mod) => mod.pushAccount(state).catch(() => undefined));
  }
}

export function updateDemo(change: (state: DemoState) => DemoState) {
  saveDemo(change(loadDemo()));
}

export function clearDemoKeepReceipt() {
  const current = loadDemo();
  saveDemo({ ...EMPTY, withdrawReceipt: current.withdrawReceipt });
}

export function useDemo(): DemoState | null {
  const [state, setState] = useState<DemoState | null>(null);
  useEffect(() => {
    const read = () => setState(loadDemo());
    void import("@/lib/account").then(async (mod) => {
      const remote = await mod.hydrateFromAuth().catch(() => null);
      if (remote) saveDemo(remote, { remote: true });
      else read();
    });
    window.addEventListener(EVENT, read);
    window.addEventListener("storage", read);
    return () => {
      window.removeEventListener(EVENT, read);
      window.removeEventListener("storage", read);
    };
  }, []);
  return state;
}

export function loadEnergyKwh(load: Load): number {
  return (load.watts / 1000) * (load.minutes / 60);
}
