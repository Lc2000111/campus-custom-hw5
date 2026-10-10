import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, CircleAlert, PartyPopper, PenLine, RotateCcw, Store, WifiOff } from "lucide-react";
import {
  api,
  API_URL,
  ApiError,
  type AgentEvent,
  type Cash,
  type PaymentRequest,
  type Run,
  type Ticket,
  type TicketDetail,
} from "./api";
import { liveStatus, money } from "./agents";
import { Till } from "./components/Till";
import { HowTo } from "./components/HowTo";
import { TicketRail } from "./components/TicketRail";
import { TicketHero } from "./components/TicketHero";
import { AgentFloor } from "./components/AgentFloor";
import { Summary } from "./components/Summary";
import { Approvals } from "./components/Approvals";
import { Feed } from "./components/Feed";

interface Toast { id: number; kind: "good" | "bad" | "info"; text: string }
interface TicketEvents { events: AgentEvent[]; lastId: number }

const POLL_MS = 1200;

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [shopToday, setShopToday] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [cash, setCash] = useState<Cash | null>(null);
  const [pending, setPending] = useState<PaymentRequest[]>([]);
  const [paid, setPaid] = useState<PaymentRequest[]>([]);
  const [eventsByTicket, setEventsByTicket] = useState<Record<number, TicketEvents>>({});
  const [lastResetId, setLastResetId] = useState(-1);
  const [run, setRun] = useState<Run | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [approver, setApproverState] = useState(() => localStorage.getItem("approver") ?? "");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [offline, setOffline] = useState<string | null>(null);
  const [confetti, setConfetti] = useState(0);
  const [flashSign, setFlashSign] = useState(false);
  const toastId = useRef(0);
  const eventsRef = useRef(eventsByTicket);
  eventsRef.current = eventsByTicket;

  const toast = useCallback((kind: Toast["kind"], text: string) => {
    const id = ++toastId.current;
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  const setApprover = (s: string) => {
    setApproverState(s);
    localStorage.setItem("approver", s);
  };

  // ---- loading -----------------------------------------------------------
  const refreshBoard = useCallback(async () => {
    try {
      const [t, c, p, pd] = await Promise.all([api.tickets(), api.cash(), api.payments("pending"), api.payments("paid")]);
      setTickets(t.tickets);
      setShopToday(t.shop_today);
      setCash(c);
      setPending(p.requests);
      setPaid(pd.requests);
      setOffline(null);
      return t.tickets;
    } catch (e) {
      if (e instanceof ApiError && e.status === 0) setOffline(e.message);
      return null;
    }
  }, []);

  const loadTicket = useCallback(async (id: number) => {
    try {
      const [d, ev] = await Promise.all([api.ticket(id), api.events({ ticketId: id })]);
      setDetail(d);
      setLastResetId(ev.last_reset_event_id);
      setEventsByTicket((m) => ({ ...m, [id]: { events: ev.events, lastId: ev.last_event_id } }));
    } catch (e) {
      if (e instanceof ApiError) toast("bad", e.message);
    }
  }, [toast]);

  useEffect(() => {
    (async () => {
      const list = await refreshBoard();
      const runs = await api.runs().catch(() => null);
      const active = runs?.runs.find((r) => r.run_id === runs.active_run);
      if (active) {
        setRun(active);
        setSelectedId(active.ticket_id);
      } else if (list?.length) {
        const fromUrl = Number(new URLSearchParams(location.hash.slice(1)).get("ticket"));
        const pick = list.find((t) => t.id === fromUrl) ?? list.find((t) => t.state === "open") ?? list[0];
        setSelectedId(pick.id);
      }
    })();
  }, [refreshBoard]);

  useEffect(() => {
    if (selectedId === null) return;
    history.replaceState(null, "", `#ticket=${selectedId}`); // reload / share keeps the same ticket
    loadTicket(selectedId);
  }, [selectedId, loadTicket]);

  // Gentle background refresh so CLI runs / approvals also show up.
  useEffect(() => {
    if (run) return;
    const t = setInterval(refreshBoard, 8000);
    return () => clearInterval(t);
  }, [run, refreshBoard]);

  // ---- live run polling -------------------------------------------------
  useEffect(() => {
    if (!run) return;
    const started = new Date(run.started_at).getTime();
    let stopped = false;
    let ticks = 0;
    const timer = setInterval(async () => {
      if (stopped) return;
      setElapsed(Math.max(0, Math.round((Date.now() - started) / 1000)));
      ticks += 1;
      try {
        const id = run.ticket_id;
        const after = eventsRef.current[id]?.lastId;
        const ev = await api.events({ ticketId: id, after });
        if (ev.events.length || after === undefined) {
          setEventsByTicket((m) => {
            const prev = m[id]?.events ?? [];
            return { ...m, [id]: { events: [...prev, ...ev.events], lastId: ev.last_event_id } };
          });
        }
        if (ticks % 3 === 0) {
          const [c, p] = await Promise.all([api.cash(), api.payments("pending")]);
          setCash(c);
          setPending(p.requests);
        }
        const status = await api.run(run.run_id);
        if (status.status !== "running") {
          stopped = true;
          setRun(null);
          await refreshBoard();
          await loadTicket(id);
          if (status.status === "done") {
            toast("good", `Ticket #${id} resolved. Check the summary and any payments waiting for you.`);
            setConfetti((n) => n + 1);
          } else {
            toast("bad", `Ticket #${id} run failed: ${status.error ?? (status.decision as { error?: string })?.error ?? "unknown error"}`);
          }
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 0) setOffline(e.message);
      }
    }, POLL_MS);
    return () => { stopped = true; clearInterval(timer); };
  }, [run, refreshBoard, loadTicket, toast]);


  // ---- actions -----------------------------------------------------------
  const goToSign = () => {
    document.getElementById("sign")?.scrollIntoView({ behavior: "smooth", block: "start" });
    setFlashSign(true);
    setTimeout(() => setFlashSign(false), 2600);
    if (!approver.trim()) setTimeout(() => document.getElementById("signature-input")?.focus(), 450);
  };

  const start = async () => {
    if (selectedId === null) return;
    try {
      const r = await api.runTicket(selectedId);
      setElapsed(0);
      setRun(r);
      toast("info", `Boss is reading ticket #${selectedId}…`);
    } catch (e) {
      toast("bad", e instanceof Error ? e.message : String(e));
    }
  };

  const approve = async (r: PaymentRequest) => {
    try {
      const res = await api.approve(r.id, approver.trim());
      toast("good", `Paid ${money(res.amount)}. Checking went from ${money(res.balance_before)} to ${money(res.balance_after)}.`);
    } catch (e) {
      toast("bad", e instanceof ApiError && e.status === 409 ? `Refused: ${e.message}` : String((e as Error).message));
    }
    await refreshBoard();
    if (selectedId !== null) loadTicket(selectedId);
  };

  const reject = async (r: PaymentRequest) => {
    try {
      await api.reject(r.id, approver.trim());
      toast("info", `Rejected request #${r.id}. No money moved.`);
    } catch (e) {
      toast("bad", (e as Error).message);
    }
    await refreshBoard();
  };

  const reset = async () => {
    if (!window.confirm("Reset the shop to the original data? Tickets reopen, checking goes back to $3,400, and requests and drafts are cleared. The audit trail is kept.")) return;
    try {
      await api.reset();
      setEventsByTicket({});
      toast("info", "Fresh start: the database is back to the original values.");
      await refreshBoard();
      if (selectedId !== null) loadTicket(selectedId);
    } catch (e) {
      toast("bad", (e as Error).message);
    }
  };

  // ---- derived -----------------------------------------------------------
  const running = run !== null && run.ticket_id === selectedId;
  const ticketEvents = useMemo(
    () => (selectedId === null ? [] : (eventsByTicket[selectedId]?.events ?? []).filter((e) => e.event_id > lastResetId)),
    [eventsByTicket, selectedId, lastResetId],
  );
  // The latest *agent* run for this ticket (human sign-offs live in their own sessions).
  const sessionEvents = useMemo(() => {
    const agentRows = ticketEvents.filter((e) => e.type !== "human_decision");
    const session = running ? run!.session_id : agentRows.reduce<AgentEvent | null>((a, e) => (!a || e.event_id > a.event_id ? e : a), null)?.session_id;
    return session ? agentRows.filter((e) => e.session_id === session) : [];
  }, [ticketEvents, running, run]);
  const feedEvents = useMemo(
    () => [...sessionEvents, ...ticketEvents.filter((e) => e.type === "human_decision")].sort((a, b) => a.event_id - b.event_id),
    [sessionEvents, ticketEvents],
  );

  const live = useMemo(() => liveStatus(sessionEvents, running), [sessionEvents, running]);
  const step: 1 | 2 | 3 = pending.length > 0 ? 3 : selectedId !== null ? 2 : 1;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark"><Store size={22} /></span>
          <div>
            <b>Campus Customs</b>
            <span>Ops Desk · shop today <strong>{shopToday || "…"}</strong></span>
          </div>
        </div>
        <HowTo step={step} onSign={goToSign} />
        <Till cash={cash} />
      </header>

      {pending.length > 0 && (
        <div className="signbar" role="alert">
          <span className="signbar__icon"><PenLine size={22} /></span>
          <div className="signbar__text">
            <b>{pending.length} payment{pending.length > 1 ? "s" : ""} need{pending.length > 1 ? "" : "s"} your signature</b>
            <span>The agents prepared them. No money moves until you sign and approve.</span>
          </div>
          <span className="signbar__total">{money(pending.reduce((s, p) => s + p.amount, 0))}</span>
          <button className="btn" onClick={goToSign}><ArrowDown size={18} /> Sign now</button>
        </div>
      )}

      {offline && (
        <div className="banner"><WifiOff size={18} /> {offline}</div>
      )}

      <main className="desk">
        <TicketRail tickets={tickets} selectedId={selectedId} runningId={run?.ticket_id ?? null} pending={pending} onSelect={setSelectedId} />

        <div className="center">
          <TicketHero detail={detail && detail.ticket.id === selectedId ? detail : null} shopToday={shopToday}
            running={running} otherRunning={run !== null && !running} elapsed={elapsed} onStart={start} />
          <AgentFloor live={live} />
          {!running && <Summary events={sessionEvents} drafts={detail?.ticket.id === selectedId ? detail.drafts : []} />}
        </div>

        <div className="side">
          <Approvals pending={pending} paid={paid} cash={cash} approver={approver} setApprover={setApprover}
            onApprove={approve} onReject={reject} flash={flashSign} />
          <Feed events={feedEvents} running={running} />
        </div>
      </main>

      <footer className="foot">
        <span>Backend <code>{API_URL}</code> · nothing is ever emailed · every payment needs a human signature</span>
        <button className="btn btn--ghost btn--small" onClick={reset} disabled={run !== null}>
          <RotateCcw size={14} /> Reset to original data
        </button>
      </footer>

      <div className="toasts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast--${t.kind}`}>
            {t.kind === "good" ? <PartyPopper size={18} /> : <CircleAlert size={18} />} {t.text}
          </div>
        ))}
      </div>

      {confetti > 0 && (
        <div className="confetti" key={confetti} aria-hidden>
          {Array.from({ length: 36 }, (_, i) => <i key={i} style={{ "--i": i } as React.CSSProperties} />)}
        </div>
      )}
    </div>
  );
}
