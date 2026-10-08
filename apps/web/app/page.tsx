"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function Home() {
  const [org, setOrg] = useState("Acme");
  const [email, setEmail] = useState("founder@acme.com");
  const [me, setMe] = useState<{ org_id: string; role: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
  }, []);

  async function signup() {
    setErr(null);
    try {
      await api.signup(org, email);
      setMe(await api.me());
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <div>
      <h1>SendPilot</h1>
      <p className="muted">
        Connect a mailbox, upload a document, review the extracted emails, and send — M0 covers
        connect + upload.
      </p>

      <div className="panel">
        {me ? (
          <div className="row">
            <span className="badge ok">signed in</span>
            <span className="muted">org {me.org_id.slice(0, 8)}… · {me.role}</span>
            <a href="/connections">Go to Connections →</a>
          </div>
        ) : (
          <>
            <h3>Create an account</h3>
            <div className="row">
              <input value={org} onChange={(e) => setOrg(e.target.value)} placeholder="Organization" />
              <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
              <button onClick={signup}>Sign up</button>
            </div>
            {err && <p className="muted">{err}</p>}
          </>
        )}
      </div>
    </div>
  );
}
