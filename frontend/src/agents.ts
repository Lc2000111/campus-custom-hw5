import {
  Boxes,
  Building2,
  Calculator,
  Crown,
  MessageCircleHeart,
  type LucideIcon,
} from "lucide-react";
import type { AgentEvent, AgentName } from "./api";

export interface AgentMeta {
  name: AgentName;
  title: string;
  role: string;
  color: string;
  icon: LucideIcon;
}

// Each agent reads differently: its own icon, colour, and a one-line job title.
export const AGENTS: Record<AgentName, AgentMeta> = {
  boss: { name: "boss", title: "Boss", role: "Reads the ticket, assigns work, makes the final call", color: "#e6197a", icon: Crown },
  inventory: { name: "inventory", title: "Inventory", role: "Stock by SKU & size, shortfalls, restock vendor", color: "#d97706", icon: Boxes },
  accounting: { name: "accounting", title: "Accounting", role: "Cash, invoices, margins, payments for approval", color: "#0f9f77", icon: Calculator },
  facilities: { name: "facilities", title: "Facilities", role: "The shop space: lease, rent, landlord", color: "#2f6fe0", icon: Building2 },
  customer_service: { name: "customer_service", title: "Customer Service", role: "Drafts friendly replies (never sent)", color: "#8b45e0", icon: MessageCircleHeart },
};

export const SPECIALISTS: AgentName[] = ["inventory", "accounting", "facilities", "customer_service"];

export function agentMeta(name: string | null | undefined): AgentMeta | undefined {
  return name && name in AGENTS ? AGENTS[name as AgentName] : undefined;
}

// Plain-English labels for MCP tools, so the feed reads like a desk, not a log file.
export const TOOL_LABELS: Record<string, string> = {
  list_tickets: "Looked over all tickets",
  list_open_tickets: "Looked over open tickets",
  get_ticket: "Read the ticket",
  update_ticket: "Updated the ticket",
  check_stock: "Checked the shelves",
  list_vendors: "Looked up vendors",
  check_vendor_hold: "Checked if the vendor will ship",
  check_rent_due: "Checked the rent",
  get_cash_position: "Checked the cash drawer",
  check_margin: "Checked the margin",
  request_payment: "Queued a payment for you to approve",
  request_purchase_order: "Queued a purchase order for you to approve",
  list_payment_requests: "Looked at pending approvals",
  save_draft: "Saved a draft reply",
  list_drafts: "Looked at drafts",
  list_queue: "Checked the work queue",
  delegate: "Handed off work",
};

export function toolLabel(tool?: string): string {
  return (tool && TOOL_LABELS[tool]) || tool || "Used a tool";
}

export type AgentState = "idle" | "thinking" | "tool" | "done" | "error";

export interface AgentLive {
  state: AgentState;
  line: string;        // what they're saying / doing right now
  tools: number;       // tool calls this session
  runs: number;        // how many times they were called in
}

const short = (s: string | null | undefined, n = 140) =>
  !s ? "" : s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;

export function describeArgs(tool: string | undefined, args: Record<string, unknown> | null | undefined): string {
  if (!args) return "";
  if (tool === "delegate") {
    const to = agentMeta(String(args.to_agent))?.title ?? String(args.to_agent);
    return `→ ${to}: ${short(String(args.task ?? ""), 110)}`;
  }
  if (tool === "save_draft") return `to ${args.recipient}: “${short(String(args.subject ?? ""), 60)}”`;
  if (tool === "update_ticket") return `status → ${args.status}`;
  const parts = Object.entries(args)
    .filter(([k]) => !["requested_by", "reason", "author_agent", "agent", "body"].includes(k))
    .map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`);
  return parts.join(" · ");
}

// Fold a session's events into one live status per agent.
export function liveStatus(events: AgentEvent[], running: boolean): Record<AgentName, AgentLive> {
  const live = Object.fromEntries(
    (Object.keys(AGENTS) as AgentName[]).map((a) => [a, { state: "idle", line: "", tools: 0, runs: 0 }]),
  ) as Record<AgentName, AgentLive>;
  for (const e of events) {
    const a = agentMeta(e.agent);
    if (!a) continue;
    const s = live[a.name];
    switch (e.type) {
      case "started":
        s.runs += 1;
        s.state = "thinking";
        s.line = e.from_agent && e.from_agent !== "human"
          ? `${agentMeta(e.from_agent)?.title ?? e.from_agent} asked: ${short(e.text, 120)}`
          : "Reading the ticket…";
        break;
      case "tool_call":
        s.tools += 1;
        s.state = "tool";
        s.line = `${toolLabel(e.tool)} ${describeArgs(e.tool, e.args)}`.trim();
        break;
      case "tool_result":
        if (s.state !== "done") s.state = "thinking";
        break;
      case "said":
        if (e.text && !e.text.trim().startsWith("{")) s.line = short(e.text, 160);
        break;
      case "finished":
        s.state = "done";
        s.line = short(e.text, 180);
        break;
      case "error":
        s.state = "error";
        s.line = short(e.text, 160);
        break;
    }
  }
  if (!running) {
    for (const s of Object.values(live)) if (s.state === "thinking" || s.state === "tool") s.state = "done";
  }
  return live;
}

export const money = (n: number | null | undefined) =>
  n === null || n === undefined
    ? "—"
    : n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
