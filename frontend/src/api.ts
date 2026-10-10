// Every call the dashboard makes goes to the FastAPI backend from Problem 7.
export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  status: string;
  state: "open" | "resolved";
  created_at: string;
}

export interface TicketsResponse {
  shop_today: string;
  tickets: Ticket[];
}

export interface TicketDetail {
  shop_today: string;
  ticket: Ticket & { notes: string | null; lease_id: number | null; invoice_id: number | null };
  linked_invoice?: { id: number; amount: number; due_date: string; status: string; vendor_name: string; days_overdue: number; description: string };
  linked_lease?: { id: number; space_name: string; landlord: string; monthly_rent: number; next_due: string };
  drafts: Draft[];
  payment_requests: PaymentRequest[];
}

export interface Draft {
  id: number;
  ticket_id: number;
  author_agent: string;
  recipient: string;
  subject: string;
  body: string;
  status: string;
}

export interface PaymentRequest {
  id: number;
  kind: "invoice" | "rent" | "purchase_order";
  ref_id: number | null;
  vendor_id: number | null;
  sku: string | null;
  size: string | null;
  qty: number | null;
  amount: number;
  ticket_id: number;
  requested_by: string;
  reason: string;
  status: "pending" | "paid" | "rejected";
  decided_by: string | null;
  decided_at: string | null;
  eta: string | null;
  label: string;
  vendor_name: string | null;
  ticket_subject: string | null;
  requester: string | null;
}

export interface Cash {
  account: string;
  balance: number;
  as_of: string;
  shop_today: string;
  pending_total: number;
  balance_after_pending: number;
}

export interface Run {
  run_id: string;
  ticket_id: number;
  status: "running" | "done" | "failed";
  session_id: string;
  started_at: string;
  finished_at?: string;
  error?: string;
  decision?: Record<string, unknown>;
}

export interface AgentEvent {
  event_id: number;
  ts: string;
  session_id: string;
  ticket_id: number | null;
  agent: string | null;
  chain: string[];
  type: "started" | "finished" | "error" | "refused" | "human_decision" | "tool_call" | "tool_result" | "said";
  text?: string | null;
  tool?: string;
  args?: Record<string, unknown> | null;
  from_agent?: string;
  output?: Record<string, unknown>;
}

export interface EventsResponse {
  last_event_id: number;
  last_reset_event_id: number;
  events: AgentEvent[];
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_URL}. Start it from backend/ with: uvicorn main:app --reload --port 8000`);
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

export const api = {
  tickets: () => request<TicketsResponse>("/api/tickets"),
  ticket: (id: number) => request<TicketDetail>(`/api/tickets/${id}`),
  runTicket: (id: number) => request<Run>(`/api/tickets/${id}/run`, { method: "POST" }),
  runs: () => request<{ active_run: string | null; runs: Run[] }>("/api/runs"),
  run: (runId: string) => request<Run>(`/api/runs/${runId}`),
  events: (params: { ticketId?: number; after?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params.ticketId !== undefined) q.set("ticket_id", String(params.ticketId));
    if (params.after !== undefined) q.set("after", String(params.after));
    q.set("limit", String(params.limit ?? 500));
    return request<EventsResponse>(`/api/events?${q}`);
  },
  payments: (status: "pending" | "paid" | "rejected" | "all" = "pending") =>
    request<{ requests: PaymentRequest[] }>(`/api/payments?status=${status}`),
  approve: (id: number, approvedBy: string) =>
    request<{ balance_before: number; balance_after: number; amount: number }>(`/api/payments/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  reject: (id: number, approvedBy: string) =>
    request<unknown>(`/api/payments/${id}/reject`, { method: "POST", body: JSON.stringify({ approved_by: approvedBy }) }),
  cash: () => request<Cash>("/api/cash"),
  reset: () => request<Cash>("/api/reset", { method: "POST" }),
};
