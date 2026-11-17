"use client";

import { AppHeader, Frame, RequireDemo } from "@/components/household/shell";
import { updateDemo, useDemo } from "@/lib/demo-store";

export default function NotificationsPage() {
  const demo = useDemo();
  return (
    <Frame>
      <RequireDemo>
        <AppHeader title="Notifications" back={{ href: "/household/settings", label: "‹" }} />
        <div className="hh-main">
          <section className="hh-card">
            <div className="hh-row">
              <div>
                <strong>Forecast alerts</strong>
                <p className="hh-fine">Stored on this browser. There is no push service.</p>
              </div>
              <button type="button" className={`hh-toggle ${demo?.notifyAlerts ? "on" : ""}`} aria-pressed={Boolean(demo?.notifyAlerts)} onClick={() => updateDemo((state) => ({ ...state, notifyAlerts: !state.notifyAlerts }))}>
                <i />
              </button>
            </div>
          </section>
          <p className="hh-note">Alerts stay derived from the forecast. Turning this off hides them in the list. It does not change a device.</p>
        </div>
      </RequireDemo>
    </Frame>
  );
}
