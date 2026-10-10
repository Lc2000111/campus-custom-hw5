import { AlertTriangle, CheckCircle2, Coffee, Wrench } from "lucide-react";
import type { AgentName } from "../api";
import { AGENTS, SPECIALISTS, type AgentLive } from "../agents";

const STATE_LABEL = { idle: "Idle", thinking: "Thinking", tool: "Working", done: "Done", error: "Stuck" } as const;

function AgentCard({ name, live, wide }: { name: AgentName; live: AgentLive; wide?: boolean }) {
  const a = AGENTS[name];
  const Icon = a.icon;
  const active = live.state === "thinking" || live.state === "tool";
  return (
    <div
      className={`agent agent--${live.state} ${wide ? "agent--boss" : ""} ${active ? "is-active" : ""}`}
      style={{ "--agent": a.color } as React.CSSProperties}
    >
      <div className="agent__head">
        <span className="agent__avatar"><Icon size={wide ? 26 : 22} /></span>
        <div className="agent__who">
          <b>{a.title}</b>
          <span>{a.role}</span>
        </div>
        <span className={`agent__state agent__state--${live.state}`}>
          {live.state === "done" ? <CheckCircle2 size={13} /> : live.state === "error" ? <AlertTriangle size={13} /> :
            live.state === "idle" ? <Coffee size={13} /> : live.state === "tool" ? <Wrench size={13} /> : null}
          {STATE_LABEL[live.state]}
          {live.state === "thinking" && <span className="dots"><i /><i /><i /></span>}
        </span>
      </div>
      <div className={`bubble ${live.line ? "" : "bubble--empty"}`}>
        {live.line || (live.state === "idle" ? "Waiting for work." : "…")}
      </div>
      <div className="agent__stats">
        <span><b>{live.tools}</b> tool call{live.tools === 1 ? "" : "s"}</span>
        <span><b>{live.runs}</b> assignment{live.runs === 1 ? "" : "s"}</span>
      </div>
    </div>
  );
}

// Boss sits at the head desk; a wire runs to each specialist and lights up while they work.
export function AgentFloor({ live }: { live: Record<AgentName, AgentLive> }) {
  return (
    <section className="floor">
      <div className="panel-title"><span>The agent team</span><span className="muted">Live while a ticket runs</span></div>
      <div className="floor__boss"><AgentCard name="boss" live={live.boss} wide /></div>
      <div className="wires" aria-hidden>
        <div className="wires__bus" />
        {SPECIALISTS.map((n) => (
          <div key={n} className={`wires__drop ${["thinking", "tool"].includes(live[n].state) ? "is-live" : ""}`}
            style={{ "--agent": AGENTS[n].color } as React.CSSProperties} />
        ))}
      </div>
      <div className="floor__team">
        {SPECIALISTS.map((n) => <AgentCard key={n} name={n} live={live[n]} />)}
      </div>
    </section>
  );
}
