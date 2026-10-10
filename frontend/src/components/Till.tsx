import { useEffect, useRef, useState } from "react";
import { Landmark, TrendingDown } from "lucide-react";
import type { Cash } from "../api";
import { money } from "../agents";

// The cash drawer: one huge number that visibly counts down when a payment is approved.
export function Till({ cash }: { cash: Cash | null }) {
  const target = cash?.balance ?? 0;
  const [shown, setShown] = useState(target);
  const [drop, setDrop] = useState<number | null>(null);
  const prev = useRef<number | null>(null);

  useEffect(() => {
    if (cash === null) return;
    const from = prev.current ?? target;
    prev.current = target;
    if (from === target) {
      setShown(target);
      return;
    }
    if (target < from) {
      setDrop(from - target);
      setTimeout(() => setDrop(null), 3200);
    }
    const start = performance.now();
    const duration = 1400;
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(from + (target - from) * eased);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, cash]);

  const low = cash !== null && cash.balance_after_pending < 0;

  return (
    <div className={`till ${drop ? "till--dropping" : ""}`} title="Checking balance from cash_accounts">
      <div className="till__label">
        <Landmark size={16} /> Checking balance
      </div>
      <div className="till__amount">{cash ? money(shown) : "—"}</div>
      {drop !== null && (
        <div className="till__drop">
          <TrendingDown size={16} /> −{money(drop)}
        </div>
      )}
      {cash && (
        <div className="till__sub">
          <span>
            Waiting for approval <b>{money(cash.pending_total)}</b>
          </span>
          <span className={low ? "bad" : ""}>
            If all approved <b>{money(cash.balance_after_pending)}</b>
          </span>
        </div>
      )}
    </div>
  );
}
