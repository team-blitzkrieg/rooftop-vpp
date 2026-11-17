"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { Button } from "@/components/household/ui";
import { loadEnergyKwh, updateDemo, useDemo, type Load } from "@/lib/demo-store";

const NAMES = ["Washing machine", "Water pump", "EV charger", "Rice cooker", "Other"];

export default function EditLoadPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const demo = useDemo();
  const creating = params.id === "new";
  const existing = demo?.loads.find((load) => load.id === params.id) ?? null;
  const [name, setName] = useState("Washing machine");
  const [watts, setWatts] = useState("2000");
  const [minutes, setMinutes] = useState("90");
  const [earliest, setEarliest] = useState("08:00");
  const [deadline, setDeadline] = useState("17:00");
  const [interruptible, setInterruptible] = useState(false);
  const [manualOnly, setManualOnly] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!existing) return;
    setName(existing.name);
    setWatts(String(existing.watts));
    setMinutes(String(existing.minutes));
    setEarliest(existing.earliest);
    setDeadline(existing.deadline);
    setInterruptible(existing.interruptible);
    setManualOnly(existing.manualOnly);
  }, [existing]);

  const draft: Load = {
    id: existing?.id ?? "draft",
    name,
    watts: Number(watts),
    minutes: Number(minutes),
    earliest,
    deadline,
    interruptible,
    manualOnly,
  };

  function save() {
    if (!name.trim() || !Number.isFinite(draft.watts) || draft.watts <= 0 || !Number.isFinite(draft.minutes) || draft.minutes <= 0) {
      setError("Enter a name, a power above 0 W, and a run time above 0 minutes.");
      return;
    }
    if (draft.earliest >= draft.deadline) {
      setError("The deadline has to be later than the earliest start.");
      return;
    }
    const saved = { ...draft, id: existing?.id ?? crypto.randomUUID(), name: name.trim() };
    updateDemo((state) => ({
      ...state,
      loads: existing ? state.loads.map((load) => (load.id === saved.id ? saved : load)) : [...state.loads, saved],
    }));
    router.push("/household/loads");
  }

  function remove() {
    if (!existing) return;
    updateDemo((state) => ({ ...state, loads: state.loads.filter((load) => load.id !== existing.id) }));
    router.push("/household/loads");
  }

  return (
    <Frame>
      <RequireDemo>
        <AppHeader
          title={creating ? "Add load" : "Edit load"}
          back={{ href: "/household/loads", label: "‹" }}
          action={<button type="button" className="hh-btn ghost" onClick={() => router.push("/household/loads")}>Cancel</button>}
        />
        <div className="hh-main">
          {!creating && demo && !existing ? <p className="hh-note">That load is not on this browser.</p> : null}
          <div className="hh-field">
            <label htmlFor="appliance">Appliance</label>
            <div className="hh-input">
              <select id="appliance" value={NAMES.includes(name) ? name : "Other"} onChange={(event) => setName(event.target.value === "Other" ? "" : event.target.value)} style={{ flex: 1, border: 0, background: "transparent", font: "inherit" }}>
                {NAMES.map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
            {!NAMES.includes(name) || name === "" ? (
              <div className="hh-input"><input aria-label="Appliance name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Appliance name" /></div>
            ) : null}
          </div>
          <div className="hh-split">
            <div className="hh-field">
              <label htmlFor="watts">Power</label>
              <div className="hh-input"><input id="watts" inputMode="numeric" value={watts} onChange={(event) => setWatts(event.target.value)} /><span className="hh-fine">W</span></div>
              <p className="hh-local">From the label on the appliance. Estimated.</p>
            </div>
            <div className="hh-field">
              <label htmlFor="minutes">Run duration</label>
              <div className="hh-input"><input id="minutes" inputMode="numeric" value={minutes} onChange={(event) => setMinutes(event.target.value)} /><span className="hh-fine">min</span></div>
            </div>
          </div>
          <div className="hh-split">
            <div className="hh-field">
              <label htmlFor="earliest">Earliest start</label>
              <div className="hh-input"><input id="earliest" type="time" value={earliest} onChange={(event) => setEarliest(event.target.value)} /></div>
            </div>
            <div className="hh-field">
              <label htmlFor="deadline">Finish by</label>
              <div className="hh-input"><input id="deadline" type="time" value={deadline} onChange={(event) => setDeadline(event.target.value)} /></div>
            </div>
          </div>
          <section className="hh-card">
            <div className="hh-row">
              <div><strong>Can be interrupted</strong><p className="hh-fine">OK to pause mid-cycle in the suggestion. The app still does not control it.</p></div>
              <button type="button" className={`hh-toggle ${interruptible ? "on" : ""}`} aria-pressed={interruptible} onClick={() => setInterruptible((value) => !value)}><i /></button>
            </div>
            <div className="hh-row">
              <div><strong>Manual-only</strong><p className="hh-fine">Keep out of the daily plan.</p></div>
              <button type="button" className={`hh-toggle ${manualOnly ? "on" : ""}`} aria-pressed={manualOnly} onClick={() => setManualOnly((value) => !value)}><i /></button>
            </div>
          </section>
          <section className="hh-card">
            <div className="hh-row">
              <span>Energy per run</span>
              <strong>{Number.isFinite(draft.watts) && Number.isFinite(draft.minutes) ? `${loadEnergyKwh(draft).toFixed(1)} kWh` : "—"}</strong>
            </div>
            <span className="hh-pill estimated">Estimated</span>
          </section>
          {error ? <p className="hh-help">{error}</p> : null}
          <Button type="button" onClick={save}>Save</Button>
          {existing ? <Button type="button" variant="danger-outline" onClick={remove}>Delete load</Button> : null}
          <p className="hh-local">Stored in this browser only.</p>
        </div>
      </RequireDemo>
    </Frame>
  );
}
