import { CalendarClock, Loader2, Play, RotateCcw, Sparkles } from "lucide-react";
import type { TicketDetail } from "../api";
import { money } from "../agents";
import { TICKET_TYPES } from "./TicketRail";

interface Props {
  detail: TicketDetail | null;
  shopToday: string;
  running: boolean;
  otherRunning: boolean;
  elapsed: number;
  onStart: () => void;
}

function daysBetween(a: string, b: string) {
  return Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86_400_000);
}

// The selected ticket, with its key numbers big enough to read across the room.
export function TicketHero({ detail, shopToday, running, otherRunning, elapsed, onStart }: Props) {
  if (!detail) {
    return (
      <section className="hero hero--empty">
        <Sparkles size={28} />
        <h2>Pick a ticket to get started</h2>
        <p>Choose any ticket on the left. Its numbers, the agent team, and the live chatter will show up here.</p>
      </section>
    );
  }
  const t = detail.ticket;
  const meta = TICKET_TYPES[t.type];
  const Icon = meta?.icon ?? Sparkles;
  const figures: { label: string; value: string; note?: string; hot?: boolean }[] = [];

  if (t.qty !== null) figures.push({ label: "Quantity", value: String(t.qty), note: `${t.sku} · size ${t.size}` });
  if (detail.linked_invoice) {
    const inv = detail.linked_invoice;
    figures.push({
      label: `Invoice #${inv.id}`,
      value: money(inv.amount),
      note: inv.status === "open" ? `${inv.days_overdue} days overdue · ${inv.vendor_name}` : `${inv.status} · ${inv.vendor_name}`,
      hot: inv.status === "open" && inv.days_overdue > 0,
    });
  }
  if (detail.linked_lease) {
    const l = detail.linked_lease;
    const days = daysBetween(shopToday, l.next_due);
    figures.push({ label: "Rent", value: money(l.monthly_rent), note: `${l.space_name} · ${l.landlord}` });
    figures.push({ label: "Due in", value: `${days} day${days === 1 ? "" : "s"}`, note: `next due ${l.next_due}`, hot: days <= 3 });
  }

  const resolved = t.status === "resolved";
  return (
    <section className={`hero ${running ? "is-running" : ""}`}>
      <div className="hero__head">
        <span className="hero__icon"><Icon size={26} /></span>
        <div>
          <div className="hero__kicker">#{t.id} · {meta?.label ?? t.type} · from {t.requester}</div>
          <h2 className="hero__title">{t.subject}</h2>
          {t.notes && <p className="hero__note">“{t.notes.split("\n")[0]}”</p>}
        </div>
        <div className="hero__action">
          <button className="btn btn--primary btn--big" onClick={onStart} disabled={running || otherRunning}
            title={otherRunning ? "Another ticket is running. One run at a time." : "Boss reads the ticket and assigns the team"}>
            {running ? <><Loader2 size={20} className="spin" /> Agents at work · {elapsed}s</> :
              resolved ? <><RotateCcw size={20} /> Run the team again</> : <><Play size={20} /> Start the agent team</>}
          </button>
          <span className="hero__hint">
            {running ? "Watch them below. Approvals will show up on the right."
              : otherRunning ? "Another ticket is running. One run at a time."
              : resolved ? "This ticket is resolved. Its summary is below."
              : "About 30–60 seconds. Nothing is sent and no money moves without you."}
          </span>
        </div>
      </div>
      {figures.length > 0 && (
        <div className="figures">
          {figures.map((f) => (
            <div key={f.label} className={`figure ${f.hot ? "figure--hot" : ""}`}>
              <span className="figure__label">{f.label}</span>
              <span className="figure__value">{f.value}</span>
              {f.note && <span className="figure__note">{f.note}</span>}
            </div>
          ))}
          <div className="figure figure--muted">
            <span className="figure__label"><CalendarClock size={13} /> Shop today</span>
            <span className="figure__value figure__value--sm">{shopToday}</span>
            <span className="figure__note">All due dates count from here</span>
          </div>
        </div>
      )}
    </section>
  );
}
