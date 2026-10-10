import { ClipboardList, Flag, Mail } from "lucide-react";
import type { AgentEvent, AgentName, Draft } from "../api";
import { AGENTS, agentMeta, toolLabel } from "../agents";

interface AgentDid {
  name: AgentName;
  summaries: string[];
  tools: Map<string, number>;
  handoffs: string[];
  actions: string[];
  approvals: string[];
  nextSteps: string[];
}

function asList(v: unknown): string[] {
  return Array.isArray(v) ? v.map(String) : [];
}

function collect(events: AgentEvent[]): AgentDid[] {
  const by = new Map<AgentName, AgentDid>();
  const get = (n: AgentName) => {
    if (!by.has(n)) by.set(n, { name: n, summaries: [], tools: new Map(), handoffs: [], actions: [], approvals: [], nextSteps: [] });
    return by.get(n)!;
  };
  for (const e of events) {
    const a = agentMeta(e.agent);
    if (!a) continue;
    const d = get(a.name);
    if (e.type === "tool_call" && e.tool) {
      if (e.tool === "delegate") {
        const to = agentMeta(String(e.args?.to_agent))?.title;
        if (to && !d.handoffs.includes(to)) d.handoffs.push(to);
      } else {
        d.tools.set(e.tool, (d.tools.get(e.tool) ?? 0) + 1);
      }
    }
    if (e.type === "finished" && e.output) {
      const o = e.output;
      const text = String(o.final_decision ?? o.summary ?? "");
      if (text) d.summaries.push(text);
      d.actions.push(...asList(o.actions_taken));
      d.approvals.push(...asList(o.needs_human_approval));
      d.nextSteps.push(...asList(o.next_steps_for_human));
      const ids = asList(o.payment_request_ids);
      if (ids.length) d.approvals.push(`Payment request ${ids.map((i) => `#${i}`).join(", ")}`);
    }
  }
  const order: AgentName[] = ["boss", "inventory", "accounting", "facilities", "customer_service"];
  return order.filter((n) => by.has(n)).map((n) => by.get(n)!);
}

// After a run: one card per agent with what it concluded, the tools it used, and who it handed off to.
export function Summary({ events, drafts }: { events: AgentEvent[]; drafts: Draft[] }) {
  const did = collect(events);
  if (did.length === 0) {
    return (
      <section className="summary summary--empty">
        <ClipboardList size={22} />
        <p>No run yet for this ticket. When the team finishes, each agent's summary will show up here.</p>
      </section>
    );
  }
  return (
    <section className="summary">
      <div className="panel-title"><span>What each agent did</span><span className="muted">from the latest run</span></div>
      <div className="summary__grid">
        {did.map((d) => {
          const a = AGENTS[d.name];
          const Icon = a.icon;
          return (
            <article key={d.name} className={`did ${d.name === "boss" ? "did--boss" : ""}`} style={{ "--agent": a.color } as React.CSSProperties}>
              <header><span className="agent__avatar agent__avatar--sm"><Icon size={16} /></span><b>{a.title}</b></header>
              {d.summaries.slice(-1).map((s, i) => <p key={i} className="did__text">{s}</p>)}
              {d.tools.size > 0 && (
                <div className="chips">
                  {[...d.tools.entries()].map(([tool, n]) => (
                    <span key={tool} className="chip" title={tool}>{toolLabel(tool)}{n > 1 ? ` ×${n}` : ""}</span>
                  ))}
                </div>
              )}
              {d.handoffs.length > 0 && <div className="did__line">Handed off to: <b>{d.handoffs.join(", ")}</b></div>}
              {d.approvals.length > 0 && <div className="did__line did__line--pink">Needs your OK: {[...new Set(d.approvals)].join(" · ")}</div>}
              {d.name === "boss" && d.nextSteps.length > 0 && (
                <ul className="did__next">{d.nextSteps.map((s, i) => <li key={i}><Flag size={12} /> {s}</li>)}</ul>
              )}
            </article>
          );
        })}
      </div>
      {drafts.length > 0 && (
        <>
          <div className="panel-title panel-title--sub"><span><Mail size={15} /> Drafts on the board</span><span className="muted">saved, never sent</span></div>
          <div className="drafts">
            {drafts.map((d) => (
              <article key={d.id} className="draft">
                <div className="draft__head">
                  <span>To <b>{d.recipient}</b></span>
                  <span className="draft__tag">Draft #{d.id} · not sent</span>
                </div>
                <div className="draft__subject">{d.subject}</div>
                <p className="draft__body">{d.body}</p>
                <div className="draft__by">Written by {agentMeta(d.author_agent)?.title ?? d.author_agent}</div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
