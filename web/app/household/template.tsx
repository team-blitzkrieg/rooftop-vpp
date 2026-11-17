"use client";

import type { ReactNode } from "react";

export default function HouseholdTemplate({ children }: { children: ReactNode }) {
  return <div className="hh-route">{children}</div>;
}
