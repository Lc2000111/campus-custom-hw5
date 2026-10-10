import { useState } from "react";
import { Building2, CheckCheck, FileText, PackagePlus, PenLine, ShieldCheck, Signature, X, type LucideIcon } from "lucide-react";
import type { Cash, PaymentRequest } from "../api";
import { agentMeta, money } from "../agents";

const KIND: Record<PaymentRequest["kind"], { icon: LucideIcon; label: string }> = {
  invoice: { icon: FileText, label: "Vendor invoice" },
  rent: { icon: Building2, label: "Rent" },
  purchase_order: { icon: PackagePlus, label: "Purchase order" },
};

interface Props {
  pending: PaymentRequest[];
  paid: PaymentRequest[];
  cash: Cash | null;
  approver: string;
  setApprover: (s: string) => void;
  onApprove: (r: PaymentRequest) => Promise<void>;
  onReject: (r: PaymentRequest) => Promise<void>;
  flash: boolean;
}

// The signature tray: the only place money moves. Approving takes two clicks on purpose.
export function Approvals({ pending, paid, cash, approver, setApprover, onApprove, onReject, flash }: Props) {
  const [confirming, setConfirming] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const act = async (r: PaymentRequest, fn: (r: PaymentRequest) => Promise<void>) => {
    setBusy(r.id);
    try { await fn(r); } finally { setBusy(null); setConfirming(null); }
  };

  return (
    <section id="sign" className={`tray ${pending.length ? "has-pending" : ""} ${flash ? "is-flash" : ""}`}>
      <div className="tray__head">
        <h2><PenLine size={20} /> Sign here</h2>
        <span className={`count-badge ${pending.length ? "is-hot" : ""}`}>{pending.length}</span>
      </div>
      <p className="tray__lead">
        {pending.length
          ? "Agents prepared these payments. Nothing is paid until you sign below and click Approve."
          : "Payments the agents prepare will wait here for your signature."}
      </p>

      <label className={`signature ${pending.length && !approver.trim() ? "is-empty" : ""}`}>
        <span className="signature__label"><Signature size={14} /> Your signature</span>
        <input id="signature-input" value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Type your name to sign" />
        <span className="signature__hint">Recorded as <code>approved_by</code> on every payment you approve.</span>
      </label>

      {pending.length === 0 && (
        <div className="tray__empty">
          <ShieldCheck size={22} />
          <p>Nothing to sign. When an agent prepares a payment or purchase order, it will wait here for you.</p>
        </div>
      )}

      {pending.map((r) => {
        const k = KIND[r.kind];
        const Icon = k.icon;
        const after = cash ? cash.balance - r.amount : null;
        const short = after !== null && after < 0;
        const by = agentMeta(r.requested_by);
        return (
          <article key={r.id} className={`cheque ${short ? "cheque--short" : ""}`}>
            <div className="cheque__top">
              <span className="cheque__icon"><Icon size={18} /></span>
              <span className="cheque__kind">{k.label} · request #{r.id}</span>
              <span className="cheque__ticket">ticket #{r.ticket_id}</span>
            </div>
            <div className="cheque__amount">{money(r.amount)}</div>
            <div className="cheque__label">{r.label}</div>
            {r.reason && <p className="cheque__reason">“{r.reason}”</p>}
            <div className="cheque__by" style={{ color: by?.color }}>prepared by {by?.title ?? r.requested_by}</div>
            <div className={`cheque__after ${short ? "bad" : ""}`}>
              Checking after this: <b>{after === null ? "—" : money(after)}</b>
              {short && <span> · not enough cash, so this will be refused</span>}
            </div>
            <div className="cheque__actions">
              {confirming === r.id ? (
                <button className="btn btn--primary" disabled={busy === r.id || !approver.trim()} onClick={() => act(r, onApprove)}>
                  <CheckCheck size={16} /> Yes, pay {money(r.amount)}
                </button>
              ) : (
                <button className="btn btn--primary" disabled={!approver.trim() || busy !== null}
                  title={!approver.trim() ? "Type your name above first" : ""} onClick={() => setConfirming(r.id)}>
                  <PenLine size={16} /> Approve
                </button>
              )}
              <button className="btn btn--ghost" disabled={!approver.trim() || busy !== null} onClick={() => act(r, onReject)}>
                <X size={16} /> Reject
              </button>
            </div>
            {!approver.trim() && <div className="cheque__hint">Type your name above to sign.</div>}
          </article>
        );
      })}

      {paid.length > 0 && (
        <div className="ledger">
          <div className="panel-title panel-title--sub"><span>Signed &amp; paid</span></div>
          {paid.map((p) => (
            <div key={p.id} className="ledger__row">
              <span>{p.label}</span>
              <b>−{money(p.amount)}</b>
              <small>by {p.decided_by}</small>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
