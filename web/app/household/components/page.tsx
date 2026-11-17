"use client";

import { useState } from "react";
import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { Button, Modal, Segmented, Sheet } from "@/components/household/ui";
import { SourcePill } from "@/components/household/pills";

export default function ComponentsPage() {
  const [seg, setSeg] = useState("day");
  const [sheet, setSheet] = useState(false);
  const [modal, setModal] = useState(false);
  const [on, setOn] = useState(true);
  return (
    <Frame>
      <RequireDemo>
        <AppHeader title="Component sheet" back={{ href: "/household/settings", label: "‹" }} />
        <div className="hh-main">
          <div className="hh-pills">
            <SourcePill source={{ kind: "measured", text: "Measured" }} />
            <SourcePill source={{ kind: "estimated", text: "Estimated" }} />
            <SourcePill source={{ kind: "simulated", text: "Simulated" }} />
            <SourcePill source={{ kind: "other", text: "Not available" }} />
          </div>
          <Button type="button">Primary</Button>
          <Button type="button" variant="secondary">Secondary</Button>
          <Button type="button" variant="danger">Danger</Button>
          <Button type="button" variant="danger-outline">Danger outline</Button>
          <Segmented label="Example" value={seg} onChange={setSeg} options={[{ id: "day", label: "Day" }, { id: "week", label: "Week" }]} />
          <div className="hh-row">
            <span>Toggle</span>
            <button type="button" className={`hh-toggle ${on ? "on" : ""}`} onClick={() => setOn((value) => !value)} aria-pressed={on}><i /></button>
          </div>
          <Button type="button" variant="secondary" onClick={() => setSheet(true)}>Open sheet</Button>
          <Button type="button" variant="secondary" onClick={() => setModal(true)}>Open modal</Button>
          <div className="hh-skel hh-skel-card" />
        </div>
      </RequireDemo>
      <Sheet open={sheet} title="Sheet title" onClose={() => setSheet(false)}>
        <p className="hh-note">Sheets slide up. Close returns to the sheet page.</p>
        <Button type="button" onClick={() => setSheet(false)}>Continue</Button>
      </Sheet>
      <Modal open={modal} title="Confirm change?" onClose={() => setModal(false)}>
        <p className="hh-note">Modals name the change before it happens.</p>
        <div className="hh-actions">
          <Button type="button" variant="secondary" onClick={() => setModal(false)}>Cancel</Button>
          <Button type="button" onClick={() => setModal(false)}>Confirm</Button>
        </div>
      </Modal>
    </Frame>
  );
}
