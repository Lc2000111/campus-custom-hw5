"""The agent loop: run an agent step by step, audit every step, and route
delegations through the MCP work queue so every hand-off can be tracked.
"""

import hashlib
import json
from collections import defaultdict
from uuid import uuid4

from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.usage import RunUsage

from backend.agents import build_all
from backend.audit import AuditLog, truncate
from backend.config import MAX_DELEGATION_DEPTH, MAX_DELEGATIONS_PER_TICKET, PROMPTS_DIR, TICKET_USAGE_LIMITS
from backend.models import AgentName, TeamDeps


def usage_dict(usage: RunUsage) -> dict[str, int]:
    return {
        "requests": usage.requests,
        "tool_calls": usage.tool_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
    }


def describe_part(part) -> dict:
    kind = part.part_kind
    if kind == "tool-call":
        return {"kind": kind, "tool": part.tool_name, "tool_call_id": part.tool_call_id, "args": part.args_as_dict()}
    if kind == "tool-return":
        return {"kind": kind, "tool": part.tool_name, "tool_call_id": part.tool_call_id,
                "content": truncate(part.content)}
    if kind == "retry-prompt":
        return {"kind": kind, "tool": part.tool_name, "content": truncate(part.content)}
    if kind == "thinking":
        return {"kind": kind, "chars": len(part.content or "")}
    if kind in ("text", "user-prompt"):
        return {"kind": kind, "content": truncate(part.content)}
    return {"kind": kind}


def describe_node(node) -> tuple[str, dict]:
    if Agent.is_user_prompt_node(node):
        return "user_prompt", {"prompt": truncate(node.user_prompt)}
    if Agent.is_model_request_node(node):
        return "model_request", {"parts": [describe_part(p) for p in node.request.parts]}
    if Agent.is_call_tools_node(node):
        resp = node.model_response
        return "model_response", {
            "model": resp.model_name,
            "parts": [describe_part(p) for p in resp.parts],
            "step_usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
        }
    if Agent.is_end_node(node):
        return "end", {"output": node.data.output.model_dump()}
    return type(node).__name__, {}


def prompt_fingerprint(name: str) -> str:
    text = (PROMPTS_DIR / f"{name}.md").read_text() + (PROMPTS_DIR / "shop_rules.md").read_text()
    return hashlib.sha256(text.encode()).hexdigest()[:12]


class Team:
    def __init__(self, session_id: str, mcp: MCPToolset, model, audit: AuditLog):
        self.session_id = session_id
        self.mcp = mcp
        self.audit = audit
        self.agents = build_all(model, mcp)
        self.delegations: dict[int, int] = defaultdict(int)

    async def call(self, tool: str, args: dict) -> dict:
        """Orchestrator-side MCP call (queue bookkeeping, ticket listing)."""
        return await self.mcp.direct_call_tool(tool, args)

    async def run_ticket(self, ticket_id: int) -> dict:
        prompt = (f"Handle ticket {ticket_id}. Read it, delegate to the right teammates, "
                  f"make the final call, update the ticket, and return your TicketDecision.")
        return await self.run_agent("boss", prompt, ticket_id, chain=[], from_agent="human", usage=RunUsage())

    async def delegate(self, ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> dict:
        deps = ctx.deps
        if to_agent == deps.agent:
            reason = "You cannot delegate to yourself."
        elif to_agent in deps.chain:
            reason = (f"{to_agent} is already in this chain {deps.chain}; "
                      "return your report and let the caller decide.")
        elif len(deps.chain) >= MAX_DELEGATION_DEPTH:
            reason = f"Max delegation depth {MAX_DELEGATION_DEPTH} reached; finish with what you have."
        elif self.delegations[deps.ticket_id] >= MAX_DELEGATIONS_PER_TICKET:
            reason = f"Delegation budget ({MAX_DELEGATIONS_PER_TICKET}) for this ticket is used up."
        else:
            reason = None
        if reason:
            self.audit.append("delegation_refused", ticket_id=deps.ticket_id, agent=deps.agent,
                              chain=deps.chain, details={"to_agent": to_agent, "task": task, "reason": reason})
            return {"refused": reason}

        self.delegations[deps.ticket_id] += 1
        return await self.run_agent(to_agent, task, deps.ticket_id, deps.chain, deps.agent, ctx.usage)

    async def run_agent(self, name: AgentName, instruction: str, ticket_id: int,
                        chain: list[str], from_agent: str, usage: RunUsage) -> dict:
        queued = await self.call("enqueue_task", {
            "session_id": self.session_id, "ticket_id": ticket_id,
            "from_agent": from_agent, "to_agent": name, "instruction": instruction,
        })
        task_id = queued["task_id"]
        await self.call("update_task", {"task_id": task_id, "status": "running"})

        chain = chain + [name]
        deps = TeamDeps(team=self, agent=name, ticket_id=ticket_id, chain=chain, queue_task_id=task_id)
        run_id = uuid4().hex[:8]
        log = dict(ticket_id=ticket_id, agent=name, agent_run_id=run_id, queue_task_id=task_id, chain=chain)
        self.audit.append("agent_start", **log, details={
            "from_agent": from_agent, "instruction": instruction, "prompt_sha": prompt_fingerprint(name),
        }, usage=usage_dict(usage))

        try:
            async with self.agents[name].iter(
                instruction, deps=deps, usage=usage, usage_limits=TICKET_USAGE_LIMITS
            ) as run:
                step = 0
                async for node in run:
                    step += 1
                    node_kind, details = describe_node(node)
                    self.audit.append("agent_step", **log, step=step, node=node_kind,
                                      details=details, usage=usage_dict(usage))
            output = run.result.output.model_dump()
            if "agent" in output:
                output["agent"] = name  # stamp the true author; don't trust the model's label
        except Exception as exc:  # budget exceeded, model/tool failure, ...
            error = f"{type(exc).__name__}: {exc}"
            self.audit.append("agent_error", **log, details={"error": error}, usage=usage_dict(usage))
            await self.call("update_task", {"task_id": task_id, "status": "failed", "result": error})
            return {"agent": name, "error": error}

        await self.call("update_task", {"task_id": task_id, "status": "done", "result": json.dumps(output)})
        self.audit.append("agent_end", **log, details={"output": output}, usage=usage_dict(usage))
        return output
