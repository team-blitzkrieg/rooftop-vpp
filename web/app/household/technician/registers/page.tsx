"use client";

import { useState } from "react";
import { AppHeader, Frame } from "@/components/household/shell";
import { Button } from "@/components/household/ui";

const KEY = "rooftop-register-reviews";

export default function RegistersPage() {
  const [register, setRegister] = useState("voltage scale");
  const [value, setValue] = useState("");
  const [saved, setSaved] = useState("");

  function save() {
    if (!value.trim()) {
      setSaved("Enter the value you read on the inverter.");
      return;
    }
    const next = { register, value: value.trim(), at: new Date().toISOString() };
    const prior = JSON.parse(window.localStorage.getItem(KEY) || "[]") as unknown[];
    window.localStorage.setItem(KEY, JSON.stringify([...prior, next]));
    setSaved("Saved on this browser as a review request. Nothing was sent to an inverter.");
  }

  return (
    <Frame>
      <AppHeader title="Register review" back={{ href: "/household/technician", label: "‹" }} />
      <div className="hh-main">
        <p className="hh-note">Use this when a reading does not match the register map. It does not write the new value to the device.</p>
        <div className="hh-field">
          <label htmlFor="register">Which register</label>
          <div className="hh-input">
            <select id="register" value={register} onChange={(event) => setRegister(event.target.value)} style={{ flex: 1, border: 0, background: "transparent", font: "inherit" }}>
              <option>voltage scale</option>
              <option>power scale</option>
              <option>energy scale</option>
              <option>frequency</option>
            </select>
          </div>
        </div>
        <div className="hh-field">
          <label htmlFor="correct">Value read on site</label>
          <div className="hh-input"><input id="correct" value={value} onChange={(event) => setValue(event.target.value)} /></div>
        </div>
        {saved ? <p className="hh-note">{saved}</p> : null}
        <Button type="button" onClick={save}>Save review request</Button>
      </div>
    </Frame>
  );
}
