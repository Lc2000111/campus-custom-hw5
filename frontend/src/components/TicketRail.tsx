import { BadgePercent, CheckCircle2, CircleDot, KeyRound, Loader2, PenLine, ShoppingBag, type LucideIcon } from "lucide-react";
import type { PaymentRequest, Ticket } from "../api";

export const TICKET_TYPES: Record<string, { icon: LucideIcon; label: string }> = {
  customer_order: { icon: ShoppingBag, label: "Customer order" },
  rent_notice: { icon: KeyRound, label: "Rent notice" },
  price_override: { icon: BadgePercent, label: "Price override" },
};

interface Props {
  tickets: Ticket[];
  selectedId: number | null;
  runningId: number | null;
  pending: PaymentRequest[];
  onSelect: (id: number) => void;
}

// Tickets look like paper stubs on a spike; resolved ones get a rubber stamp.
export function TicketRail({ tickets, selectedId, runningId, pending, onSelect }: Props) {
  const openCount = tickets.filter((t) => t.state === "open").length;
  return (
    <aside className="rail">
      <div className="panel-title">
        <span>Tickets</span>
        <span className="count-pill">
          <b>{openCount}</b> open · <b>{tickets.length - openCount}</b> resolved
        </span>
      </div>
      {tickets.map((t) => {
        const meta = TICKET_TYPES[t.type] ?? { icon: CircleDot, label: t.type };
        const Icon = meta.icon;
        const waiting = pending.filter((p) => p.ticket_id === t.id).length;
        const running = runningId === t.id;
        return (
          <button
            key={t.id}
            className={`stub ${selectedId === t.id ? "is-selected" : ""} ${t.state === "resolved" ? "is-resolved" : ""} ${running ? "is-running" : ""}`}
            onClick={() => onSelect(t.id)}
          >
            <div className="stub__top">
              <span className="stub__icon"><Icon size={20} /></span>
              <span className="stub__id">#{t.id}</span>
              <span className={`status-pill status-pill--${running ? "running" : t.state}`}>
                {running ? <><Loader2 size={13} className="spin" /> Working</> :
                  t.state === "resolved" ? <><CheckCircle2 size={13} /> Resolved</> : <><CircleDot size={13} /> Open</>}
              </span>
            </div>
            <div className="stub__subject">{t.subject}</div>
            <div className="stub__meta">
              {meta.label} · {t.requester}
            </div>
            {t.qty !== null && (
              <div className="stub__numbers">
                <span><b>{t.qty}</b> × {t.sku}</span>
                <span>size <b>{t.size}</b></span>
              </div>
            )}
            {waiting > 0 && (
              <div className="stub__waiting"><PenLine size={13} /> {waiting} payment{waiting > 1 ? "s need" : " needs"} your signature</div>
            )}
            {t.state === "resolved" && <div className="stamp">Resolved</div>}
          </button>
        );
      })}
    </aside>
  );
}
