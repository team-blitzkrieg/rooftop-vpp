"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { IconCheck } from "@/components/household/icons";
import { Button, Modal } from "@/components/household/ui";
import { clearDemoKeepReceipt, useDemo } from "@/lib/demo-store";

export default function WithdrawnPage() {
  const demo = useDemo();
  const router = useRouter();
  const receipt = demo?.withdrawReceipt ?? null;
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (demo?.session && demo.withdrawReceipt) clearDemoKeepReceipt();
  }, [demo]);

  return (
    <main className="hh">
      <div className="hh-main">
        <div style={{ textAlign: "center", marginTop: 24 }}>
          <IconCheck size={28} stroke="#2a7130" />
          <h1>You've left the demo</h1>
          <p className="hh-note">{receipt ? `Thanks for looking, ${receipt.email.split("@")[0]}.` : "No withdrawal receipt is stored on this browser."}</p>
        </div>
        {receipt ? (
          <section className="hh-card">
            <div className="hh-row"><h2>Receipt</h2><span className="hh-pill none">{receipt.id}</span></div>
            <p className="hh-note">Cleared {new Date(receipt.at).toLocaleString("en-GB", { timeZone: "Asia/Colombo" })}</p>
            <p className="hh-note">Supabase forecasts were not deleted. No edge unit was contacted. The local demo state on this browser was cleared.</p>
            <p className="hh-local">A 30-day deletion date is not scheduled, because no personal rows were written to the database.</p>
          </section>
        ) : null}
        <Button type="button" variant="secondary" onClick={() => setOpen(true)}>Download receipt (PDF)</Button>
        <Button type="button" onClick={() => router.push("/household/sign-in")}>Done</Button>
      </div>
      <Modal open={open} title="Receipt download" onClose={() => setOpen(false)}>
        <p className="hh-note">A PDF is not generated. The card on this page is the local receipt.</p>
        <Button type="button" onClick={() => setOpen(false)}>Close</Button>
      </Modal>
    </main>
  );
}
