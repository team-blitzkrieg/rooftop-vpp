"use client";

import Link from "next/link";
import { useState } from "react";
import { AppHeader, Frame } from "@/components/household/shell";

const BRANDS = [
  { name: "Huawei", how: "Modbus TCP through the Smart Dongle, or RS485. Installer-reported, not measured." },
  { name: "Growatt", how: "RS485 Modbus RTU. Installer-reported, not measured." },
  { name: "Solax", how: "Modbus over RS485 or a LAN dongle. Installer-reported, not measured." },
  { name: "Sungrow", how: "Modbus TCP through the WiNet dongle. Installer-reported, not measured." },
  { name: "Unknown", how: "Use an external meter. Do not guess a register map." },
];

export default function TechnicianPage() {
  const [brand, setBrand] = useState(BRANDS[0].name);
  const chosen = BRANDS.find((item) => item.name === brand) ?? BRANDS[0];
  return (
    <Frame>
      <AppHeader title="Technician" back={{ href: "/household/settings", label: "‹" }} />
      <div className="hh-main">
        <section className="hh-card">
          <h2>Start of a visit</h2>
          <p className="hh-note">Work on the AC side and on the edge unit only. Never open the inverter or touch DC.</p>
        </section>
        <div className="hh-field">
          <label htmlFor="brand">Inverter brand</label>
          <div className="hh-input">
            <select id="brand" value={brand} onChange={(event) => setBrand(event.target.value)} style={{ flex: 1, border: 0, background: "transparent", font: "inherit" }}>
              {BRANDS.map((item) => <option key={item.name}>{item.name}</option>)}
            </select>
          </div>
          <p className="hh-note">{chosen.how}</p>
        </div>
        <Link className="hh-link" href="/household/technician/registers">Register does not match</Link>
        <Link className="hh-link" href="/household/technician/bench">Bench limits</Link>
        <Link className="hh-link" href="/household/settings-check">Settings check</Link>
      </div>
    </Frame>
  );
}
