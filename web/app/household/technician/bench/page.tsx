"use client";

import { useState } from "react";
import { AppHeader, Frame } from "@/components/household/shell";
import { Button, Modal } from "@/components/household/ui";

export default function BenchPage() {
  const [exportLimit, setExportLimit] = useState("50");
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const limit = Number(exportLimit);
  const allowed = Number.isFinite(limit) && limit >= 0 && limit <= 100;

  return (
    <Frame>
      <AppHeader title="Bench limits" back={{ href: "/household/technician", label: "‹" }} />
      <div className="hh-main">
        <div className="hh-banner warn">
          <div>
            <strong>Lab rig only</strong>
            <p>This pilot app will not send a command. Control stays on the bench, and this form does not leave the browser.</p>
          </div>
        </div>
        <div className="hh-field">
          <label htmlFor="limit">Export limit, percent</label>
          <div className="hh-input"><input id="limit" inputMode="numeric" value={exportLimit} onChange={(event) => setExportLimit(event.target.value)} /></div>
          <p className="hh-local">Allowed range 0 to 100. Free typing of a command is not offered.</p>
        </div>
        {note ? <p className="hh-note">{note}</p> : null}
        <Button type="button" onClick={() => (allowed ? setOpen(true) : setNote("Keep the limit between 0 and 100."))}>Review</Button>
      </div>
      <Modal open={open} title="Confirm bench note?" onClose={() => setOpen(false)}>
        <p className="hh-note">This records export limit {limit}% as a lab note. No inverter is contacted. Homes stay in Advice mode.</p>
        <div className="hh-actions">
          <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
          <Button type="button" onClick={() => { setNote(`Noted ${limit}% for the lab rig. Not sent.`); setOpen(false); }}>Confirm</Button>
        </div>
      </Modal>
    </Frame>
  );
}
