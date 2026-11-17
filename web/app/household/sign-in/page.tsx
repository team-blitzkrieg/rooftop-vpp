"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { IconAlert, IconEye, IconLock, IconMail, IconSun } from "@/components/household/icons";
import { Button, Modal } from "@/components/household/ui";
import { updateDemo } from "@/lib/demo-store";

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [attempts, setAttempts] = useState(0);
  const [modal, setModal] = useState<"forgot" | "request" | null>(null);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
    if (!validEmail || password.length < 8) {
      setAttempts((count) => count + 1);
      setError("Wrong email or password");
      return;
    }
    updateDemo((state) => ({
      ...state,
      session: { email: email.trim(), signedInAt: new Date().toISOString() },
      withdrawReceipt: null,
    }));
    router.push("/household/welcome");
  }

  return (
    <main className="hh">
      <form className="hh-auth" onSubmit={submit}>
        <div className="hh-mark">
          <IconSun size={32} stroke="#a14a07" />
        </div>
        <h1 className="hh-center-title">Rooftops to Power Plant</h1>
        <p className="hh-center-sub">Household pilot · Team Blitzkrieg</p>
        <p className="hh-local" style={{ textAlign: "center" }}>
          Demo sign-in. It is stored in this browser and does not create a Supabase account.
        </p>
        {error ? (
          <div className="hh-banner">
            <IconAlert size={18} stroke="#b71c1c" />
            <div>
              <strong>{error}</strong>
              <p>Check both and try again. {attempts} of 5 attempts used. Use a real-looking email and at least 8 characters.</p>
            </div>
          </div>
        ) : null}
        <div className="hh-field">
          <label htmlFor="email">Email</label>
          <div className={`hh-input ${error ? "err" : ""}`}>
            <IconMail size={16} stroke="#6b7280" />
            <input id="email" type="email" autoComplete="username" placeholder="name@example.lk" value={email} onChange={(event) => setEmail(event.target.value)} />
          </div>
        </div>
        <div className="hh-field">
          <label htmlFor="password">Password</label>
          <div className={`hh-input ${error ? "err" : ""}`}>
            <IconLock size={16} stroke="#6b7280" />
            <input id="password" type={show ? "text" : "password"} autoComplete="current-password" placeholder="Enter your password" value={password} onChange={(event) => setPassword(event.target.value)} />
            <button type="button" className="hh-icon-btn" aria-label={show ? "Hide password" : "Show password"} onClick={() => setShow((value) => !value)}>
              <IconEye size={16} />
            </button>
          </div>
          {error ? <p className="hh-help">{error}</p> : null}
        </div>
        <div style={{ textAlign: "right" }}>
          <button type="button" className="hh-btn ghost" onClick={() => setModal("forgot")}>
            Forgot password?
          </button>
        </div>
        <Button type="submit">Sign in</Button>
        <div className="hh-note" style={{ textAlign: "center" }}>
          Not in the pilot yet?
          <button type="button" className="hh-btn ghost" onClick={() => setModal("request")}>
            Request pilot credentials
          </button>
        </div>
        <a className="hh-link" href="/household/help" style={{ textAlign: "center" }}>Help and contact</a>
        <p className="hh-note" style={{ marginTop: "auto", textAlign: "center" }}>
          Read-only pilot · we never switch or control your devices.
        </p>
      </form>
      <Modal open={modal === "forgot"} title="Password reset is not available" onClose={() => setModal(null)}>
        <p className="hh-note">This demo does not send email. Sign in with any email and a password of at least 8 characters.</p>
        <Button type="button" onClick={() => setModal(null)}>Close</Button>
      </Modal>
      <Modal open={modal === "request"} title="Demo credentials" onClose={() => setModal(null)}>
        <p className="hh-note">No pilot account is issued here. The sign-in form accepts any email and a password of 8 or more characters, then keeps that session on this browser.</p>
        <Button type="button" onClick={() => setModal(null)}>Close</Button>
      </Modal>
    </main>
  );
}
