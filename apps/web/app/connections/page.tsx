"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";

type Conn = { id: string; provider: string; account_email: string; status: string };

export default function Connections() {
  const [conns, setConns] = useState<Conn[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [showCustom, setShowCustom] = useState(false);

  const refresh = useCallback(() => {
    api.listConnections().then(setConns).catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function connect(starter: () => Promise<{ auth_url: string }>) {
    try {
      const { auth_url } = await starter();
      window.location.href = auth_url;
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <div>
      <h1>Connections</h1>
      <p className="muted">Connect the mailboxes SendPilot can send from. You pick which one per send.</p>

      <div className="panel">
        <div className="row">
          <button onClick={() => connect(api.startGoogle)}>Connect Gmail</button>
          <button onClick={() => connect(api.startMicrosoft)}>Connect Microsoft 365</button>
          <button className="secondary" onClick={() => setShowCustom((s) => !s)}>
            + Add Gmail with its own app
          </button>
          <button className="secondary" onClick={refresh}>Refresh</button>
        </div>

        {showCustom && (
          <div style={{ marginTop: 14, borderTop: "1px solid var(--border)", paddingTop: 14 }}>
            <p className="muted" style={{ marginTop: 0 }}>
              For an inbox on a different domain/Google project: paste that account&apos;s OAuth
              <b> Client ID</b> and <b>Client secret</b> (redirect URI must be
              <code> http://localhost:8080/v1/connections/google/callback</code>), then sign in as
              that email on the next screen.
            </p>
            <div className="row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
              <input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="Client ID" />
              <input value={clientSecret} onChange={(e) => setClientSecret(e.target.value)} placeholder="Client secret" />
              <div className="row">
                <button
                  onClick={() => connect(() => api.startGoogle({ client_id: clientId.trim(), client_secret: clientSecret.trim() }))}
                  disabled={!clientId.trim() || !clientSecret.trim()}
                >
                  Connect this Gmail
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {err && <p className="muted">{err}</p>}

      <div className="panel">
        {conns.length === 0 ? (
          <p className="muted">No mailboxes connected yet.</p>
        ) : (
          <table>
            <thead><tr><th>Provider</th><th>Account</th><th>Status</th></tr></thead>
            <tbody>
              {conns.map((c) => (
                <tr key={c.id}>
                  <td>{c.provider}</td>
                  <td>{c.account_email}</td>
                  <td><span className="badge ok">{c.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
