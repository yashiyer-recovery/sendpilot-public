"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";

type Extraction = {
  id: string;
  filename: string;
  status: string;
  shape: string;
  record_count: number;
  needs_review_count: number;
  created_at: string;
};

export default function Documents() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [recent, setRecent] = useState<Extraction[]>([]);

  const loadRecent = useCallback(() => {
    api.listExtractions().then(setRecent).catch(() => {});
  }, []);

  useEffect(() => { loadRecent(); }, [loadRecent]);

  async function upload() {
    setErr(null);
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    try {
      setBusy(true);
      const { document_id } = await api.upload(file);
      setDocId(document_id);
      for (let i = 0; i < 30; i++) {
        const doc = await api.getDocument(document_id);
        setStatus(doc.status);
        if (doc.status === "ready" || doc.status === "rejected") break;
        await new Promise((r) => setTimeout(r, 1000));
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function extract() {
    if (!docId) return;
    try {
      setBusy(true);
      const { extraction_job_id } = await api.startExtraction(docId);
      for (let i = 0; i < 60; i++) {
        const job = await api.getExtraction(extraction_job_id);
        if (job.status === "completed") {
          router.push(`/extractions/${extraction_job_id}`);
          return;
        }
        if (job.status === "failed") { setErr("extraction failed"); return; }
        await new Promise((r) => setTimeout(r, 1000));
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
      loadRecent();
    }
  }

  return (
    <div>
      <h1>Documents</h1>
      <p className="muted">Upload an Excel/CSV/DOCX/PDF with the emails to send.</p>

      <div className="panel">
        <div className="row">
          <input ref={fileRef} type="file" />
          <button onClick={upload} disabled={busy}>Upload</button>
          {status === "ready" && (
            <button onClick={extract} disabled={busy}>Run extraction →</button>
          )}
        </div>
        {docId && (
          <p className="muted">{docId.slice(0, 8)}… → <span className="badge">{status}</span></p>
        )}
        {err && <p className="muted">{err}</p>}
      </div>

      <div className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3 style={{ margin: 0 }}>Recent extractions</h3>
          <button className="secondary" onClick={loadRecent}>Refresh</button>
        </div>
        {recent.length === 0 ? (
          <p className="muted">Nothing yet — upload a file above.</p>
        ) : (
          <table>
            <thead>
              <tr><th>File</th><th>Status</th><th>Records</th><th>Needs review</th><th></th></tr>
            </thead>
            <tbody>
              {recent.map((x) => (
                <tr key={x.id}>
                  <td>{x.filename}</td>
                  <td><span className="badge">{x.status}</span></td>
                  <td>{x.record_count}</td>
                  <td>{x.needs_review_count}</td>
                  <td>
                    {x.status === "completed" ? (
                      <Link href={`/extractions/${x.id}`}>Review →</Link>
                    ) : (
                      <span className="muted">{x.status}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
