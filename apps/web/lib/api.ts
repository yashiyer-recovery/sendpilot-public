// Thin typed API client. Cookies (the session) are sent with credentials:include.
// M1 review surface; a later milestone swaps this for an OpenAPI-generated client.

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type ApiError = { code: string; message: string; request_id: string };

export type Record = {
  id: string;
  recipient_email: string | null;
  recipient_name: string | null;
  subject: string | null;
  body: string | null;
  body_format: string;
  confidence: number;
  validation_status: string;
  review_status: string;
  source_ref: { document_id?: string; location?: string };
};

export type Job = {
  id: string;
  status: string;
  shape: string;
  record_count: number;
  needs_review_count: number;
};

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const err: ApiError = body?.error ?? { code: "internal", message: res.statusText, request_id: "-" };
    throw new Error(`${err.code}: ${err.message}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  base: BASE,
  signup: (org_name: string, email: string) =>
    req<{ org_id: string; user_id: string; role: string }>("/v1/auth/signup", {
      method: "POST",
      body: JSON.stringify({ org_name, email }),
    }),
  me: () => req<{ org_id: string; role: string }>("/v1/auth/me"),
  startGoogle: (creds?: { client_id: string; client_secret: string }) =>
    req<{ auth_url: string }>("/v1/connections/google/start", {
      method: "POST",
      body: JSON.stringify(creds ?? {}),
    }),
  startMicrosoft: () => req<{ auth_url: string }>("/v1/connections/microsoft/start", { method: "POST" }),
  listConnections: () =>
    req<{ id: string; provider: string; account_email: string; status: string }[]>("/v1/connections"),

  async upload(file: File) {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/v1/documents`, { method: "POST", credentials: "include", body: form });
    if (!res.ok) throw new Error("upload failed");
    return (await res.json()) as { document_id: string; status: string };
  },
  getDocument: (id: string) =>
    req<{ id: string; status: string; filename: string }>(`/v1/documents/${id}`),

  startExtraction: (docId: string) =>
    req<{ extraction_job_id: string; status: string }>(`/v1/documents/${docId}/extractions`, { method: "POST" }),
  getExtraction: (jobId: string) => req<Job>(`/v1/extractions/${jobId}`),
  listExtractions: () =>
    req<
      { id: string; filename: string; status: string; shape: string; record_count: number; needs_review_count: number; created_at: string }[]
    >("/v1/extractions"),
  getRecords: (jobId: string, status?: string, cursor?: string) => {
    const q = new URLSearchParams();
    if (status) q.set("status", status);
    if (cursor) q.set("cursor", cursor);
    return req<{ records: Record[]; next_cursor: string | null }>(
      `/v1/extractions/${jobId}/records?${q.toString()}`,
    );
  },
  patchRecord: (id: string, fields: Partial<Pick<Record, "subject" | "body" | "recipient_email">>) =>
    req<Record>(`/v1/records/${id}`, { method: "PATCH", body: JSON.stringify(fields) }),
  approveRecord: (id: string) => req(`/v1/records/${id}/approve`, { method: "POST" }),
  bulkApprove: (ids: string[]) =>
    req<{ approved: number }>("/v1/records:bulk_approve", {
      method: "POST",
      body: JSON.stringify({ record_ids: ids }),
    }),
  approveAll: (jobId: string) =>
    req<{ approved: number }>(`/v1/extractions/${jobId}/approve_all`, { method: "POST" }),

  createCampaign: (name: string, connected_account_id: string, record_ids: string[]) =>
    req<{ id: string; status: string }>("/v1/campaigns", {
      method: "POST",
      body: JSON.stringify({ name, connected_account_id, record_ids }),
    }),
  sendCampaign: (id: string) =>
    req<{ enqueued: number; skipped_unapproved: number; skipped_already_sent: number }>(
      `/v1/campaigns/${id}/send`,
      { method: "POST", body: JSON.stringify({ mode: "now" }) },
    ),
  getMessages: (campaignId: string) =>
    req<{ id: string; status: string; error: string | null }[]>(`/v1/messages?campaign_id=${campaignId}`),
};
