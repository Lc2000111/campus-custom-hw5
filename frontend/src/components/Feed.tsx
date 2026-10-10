import { ArrowRight, CheckCircle2, PenLine, Radio } from "lucide-react";
import type { AgentEvent } from "../api";
import { agentMeta, describeArgs, money, toolLabel } from "../agents";

function time(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Desk chatter: every hand-off, tool call and final word, newest first.
export function Feed({ events, running }: { events: AgentEvent[]; running: boolean }) {
  // Tool results are long JSON; the summary and agent cards already show what they meant.
  const shown = events
    .filter((e) => e.type !== "tool_result" && !(e.type === "said" && e.text?.trim().startsWith("{")))
    .reverse()
    .slice(0, 120);
  return (
    <section className="feed">
      <div className="panel-title">
        <span><Radio size={16} className={running ? "pulse" : ""} /> Desk chatter</span>
        <span className="muted">{running ? "live" : `${shown.length} steps`}</span>
      </div>
      {shown.length === 0 && <p className="feed__empty">Quiet so far. Start the team and every step will stream in here.</p>}
      <ol className="feed__list">
        {shown.map((e, i) => {
          const a = agentMeta(e.agent);
          const color = a?.color ?? "#999";
          let body: React.ReactNode = null;
          if (e.type === "started") {
            const from = agentMeta(e.from_agent);
            body = from
              ? <><b style={{ color: from.color }}>{from.title}</b> <ArrowRight size={12} /> <b style={{ color }}>{a?.title}</b> <span className="feed__text">{e.text}</span></>
              : <><b style={{ color }}>{a?.title}</b> picked up the ticket</>;
          } else if (e.type === "tool_call") {
            body = <><b style={{ color }}>{a?.title}</b> {toolLabel(e.tool)} <span className="feed__args">{describeArgs(e.tool, e.args)}</span></>;
          } else if (e.type === "said") {
            body = <><b style={{ color }}>{a?.title}</b> <span className="feed__text">“{e.text}”</span></>;
          } else if (e.type === "finished") {
            body = <><CheckCircle2 size={13} style={{ color }} /> <b style={{ color }}>{a?.title}</b> finished: <span className="feed__text">{e.text}</span></>;
          } else if (e.type === "human_decision") {
            body = <HumanLine text={e.text} />;
          } else {
            body = <><b style={{ color }}>{a?.title ?? e.agent}</b> {e.type}: {e.text}</>;
          }
          return (
            <li key={`${e.event_id}-${i}`} className={`feed__item feed__item--${e.type}`} style={{ "--agent": e.type === "human_decision" ? "#1a1220" : color } as React.CSSProperties}>
              <span className="feed__dot" />
              <div className="feed__body">{body}</div>
              <time>{time(e.ts)}</time>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

// A human signature, e.g. "Josh Liang approved request #1 · $840.00 · checking $3,400.00 → $2,560.00".
function HumanLine({ text }: { text?: string | null }) {
  let d: { request_id?: number; decision?: string; approved_by?: string; result?: { amount?: number; balance_before?: number; balance_after?: number; refused?: boolean; reason?: string } } = {};
  try { d = JSON.parse(text ?? "{}"); } catch { /* show raw below */ }
  const r = d.result ?? {};
  return (
    <>
      <PenLine size={13} /> <b>{d.approved_by ?? "Human"}</b> {d.decision === "approve" ? (r.refused ? "tried to approve" : "approved") : "rejected"} request #{d.request_id}
      {r.amount !== undefined && <> · <b>{money(r.amount)}</b></>}
      {r.balance_after !== undefined && <span className="feed__args"> · checking {money(r.balance_before)} → {money(r.balance_after)}</span>}
      {r.refused && <span className="feed__args"> · refused: {r.reason}</span>}
    </>
  );
}
