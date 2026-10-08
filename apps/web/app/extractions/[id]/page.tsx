"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, type Record } from "../../../lib/api";

type Conn = { id: string; provider: string; account_email: string; status: string };

function confidenceClass(c: number): string {
  return c >= 0.85 ? "ok" : "";
}

export default function Review() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;

  const [records, setRecords] = useState<Record[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<string | null>(null);
  const [conns, setConns] = useState<Conn[]>([]);
  const [account, setAccount] = useState<string>("");
  const [name, setName] = useState("Outreach");
  const [sendResult, setSendResult] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const c = await api.listConnections();
      setConns(c);
      // Default to the most recently connected mailbox (your real account, not a leftover mock).
      if (c.length) setAccount((a) => a || c[c.length - 1].id);
      // Load ALL records, paging through the cursor (handles >50 records).
      let all: Record[] = [];
      let cursor: string | undefined;
      do {
        const page = await api.getRecords(jobId, undefined, cursor);
        all = all.concat(page.records);
        cursor = page.next_cursor ?? undefined;
      } while (cursor);
      setRecords(all);
    } catch (e) {
      setErr(String(e));
    }
  }, [jobId]);

  useEffect(() => { load(); }, [load]);

  function toggle(id: string) {
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  }

  async function saveRow(r: Record, subject: string, body: string, email: string) {
    const updated = await api.patchRecord(r.id, { subject, body, recipient_email: email });
    setRecords((rs) => rs.map((x) => (x.id === r.id ? updated : x)));
    setExpanded(null);
  }

  async function approve(id: string) {
    await api.approveRecord(id);
    setRecords((rs) => rs.map((x) => (x.id === id ? { ...x, review_status: "approved" } : x)));
  }

  async function bulkApprove() {
    const ids = [...selected];
    if (!ids.length) return;
    await api.bulkApprove(ids);
    setRecords((rs) => rs.map((x) => (selected.has(x.id) ? { ...x, review_status: "approved" } : x)));
    setSelected(new Set());
  }

  async function approveAll() {
    await api.approveAll(jobId);
    setRecords((rs) => rs.map((x) => ({ ...x, review_status: "approved" })));
  }

  async function sendApproved() {
    setErr(null);
    setSendResult(null);
    const approvedIds = records.filter((r) => r.review_status === "approved").map((r) => r.id);
    if (!approvedIds.length || !account) {
      setErr("Approve at least one record and pick a sending account.");
      return;
    }
    const acct = conns.find((c) => c.id === account);
    const ok = window.confirm(
      `Send ${approvedIds.length} real email${approvedIds.length === 1 ? "" : "s"} from ` +
      `${acct?.account_email ?? "this account"}?\n\nThis sends immediately and CANNOT be undone.`,
    );
    if (!ok) return;
    try {
      const { id } = await api.createCampaign(name, account, approvedIds);
      const res = await api.sendCampaign(id);
      let statuses: string[] = [];
      for (let i = 0; i < 30; i++) {
        const msgs = await api.getMessages(id);
        statuses = msgs.map((m) => m.status);
        if (msgs.length && statuses.every((s) => ["sent", "failed", "skipped"].includes(s))) break;
        await new Promise((r) => setTimeout(r, 1000));
      }
      const sent = statuses.filter((s) => s === "sent").length;
      setSendResult(
        `Sent ${sent} · skipped ${res.skipped_already_sent} already-emailed · ` +
        `${res.skipped_unapproved} unapproved`,
      );
    } catch (e) {
      setErr(String(e));
    }
  }

  const approvedCount = records.filter((r) => r.review_status === "approved").length;

  return (
    <div>
      <h1>Review &amp; approve</h1>
      <p className="muted">
        {records.length} records · {approvedCount} approved. Edit any record to re-run validation;
        only approved records can be sent.
      </p>

      <div className="panel">
        <div className="row">
          <button onClick={approveAll} disabled={!records.length}>
            Approve all ({records.length})
          </button>
          <button className="secondary" onClick={bulkApprove} disabled={!selected.size}>
            Approve selected ({selected.size})
          </button>
          <span style={{ flex: 1 }} />
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Campaign name" />
          <select value={account} onChange={(e) => setAccount(e.target.value)}>
            {conns.map((c) => (
              <option key={c.id} value={c.id}>{c.account_email}</option>
            ))}
          </select>
          <button onClick={sendApproved} disabled={!approvedCount}>Send approved ({approvedCount})</button>
        </div>
        {sendResult && <p className="badge ok" style={{ marginTop: 10 }}>{sendResult}</p>}
        {err && <p className="muted">{err}</p>}
      </div>

      <div className="panel">
        <table>
          <thead>
            <tr>
              <th></th><th>Recipient</th><th>Subject</th><th>Conf.</th>
              <th>Validation</th><th>Review</th><th>Source</th><th></th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <RowView
                key={r.id}
                r={r}
                checked={selected.has(r.id)}
                expanded={expanded === r.id}
                onToggle={() => toggle(r.id)}
                onExpand={() => setExpanded(expanded === r.id ? null : r.id)}
                onSave={saveRow}
                onApprove={() => approve(r.id)}
              />
            ))}
          </tbody>
        </table>
        {records.length === 0 && <p className="muted">No records yet.</p>}
      </div>
    </div>
  );
}

function RowView(props: {
  r: Record;
  checked: boolean;
  expanded: boolean;
  onToggle: () => void;
  onExpand: () => void;
  onSave: (r: Record, subject: string, body: string, email: string) => void;
  onApprove: () => void;
}) {
  const { r } = props;
  const [subject, setSubject] = useState(r.subject ?? "");
  const [body, setBody] = useState(r.body ?? "");
  const [email, setEmail] = useState(r.recipient_email ?? "");

  return (
    <>
      <tr>
        <td><input type="checkbox" checked={props.checked} onChange={props.onToggle} /></td>
        <td>{r.recipient_email}</td>
        <td>{r.subject}</td>
        <td><span className={`badge ${confidenceClass(r.confidence)}`}>{r.confidence.toFixed(2)}</span></td>
        <td><span className="badge">{r.validation_status}</span></td>
        <td><span className={`badge ${r.review_status === "approved" ? "ok" : ""}`}>{r.review_status}</span></td>
        <td className="muted">{r.source_ref?.location ?? "—"}</td>
        <td>
          <button className="secondary" onClick={props.onExpand}>Edit</button>{" "}
          <button onClick={props.onApprove} disabled={r.review_status === "approved"}>Approve</button>
        </td>
      </tr>
      {props.expanded && (
        <tr>
          <td colSpan={8}>
            <div className="row" style={{ flexDirection: "column", alignItems: "stretch" }}>
              <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Recipient" />
              <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject" />
              <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={5}
                        style={{ width: "100%", background: "#0e1218", color: "var(--text)",
                                 border: "1px solid var(--border)", borderRadius: 8, padding: 10 }} />
              <div className="row">
                <button onClick={() => props.onSave(r, subject, body, email)}>Save &amp; revalidate</button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
