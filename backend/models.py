"""Data types shared by the Campus Customs agent team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.team import Team

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal["open", "in_progress", "waiting_approval", "waiting_vendor", "resolved"]


class AgentReport(BaseModel):
    """What a specialist agent hands back to whoever delegated to it."""

    agent: AgentName
    summary: str = Field(description="One or two sentences: what you found and did.")
    facts: list[str] = Field(description="Facts you used, each taken from a tool result (cite the tool).")
    recommendation: str = Field(description="What you recommend the caller or Boss decide.")
    actions_taken: list[str] = Field(default_factory=list, description="Writes you made, with ids (request_id, draft_id).")
    needs_human_approval: list[str] = Field(default_factory=list, description="Payment/PO request ids awaiting a human.")
    open_questions: list[str] = Field(default_factory=list)


class TicketDecision(BaseModel):
    """Boss's final call on one ticket."""

    ticket_id: int
    assigned_agents: list[AgentName]
    final_decision: str = Field(description="The call Boss made and why, in plain language.")
    ticket_status: TicketStatus
    payment_request_ids: list[int] = Field(default_factory=list, description="Requests waiting on a human.")
    draft_ids: list[int] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_steps_for_human: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    """One line in output/audit_trail.json."""

    ts: str
    session_id: str
    event: Literal[
        "session_start", "agent_start", "agent_step", "agent_end", "agent_error",
        "delegation_refused", "human_decision", "database_reset", "session_end",
    ]
    ticket_id: int | None = None
    agent: str | None = None
    agent_run_id: str | None = None
    queue_task_id: int | None = None
    chain: list[str] = Field(default_factory=list)
    step: int | None = None
    node: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, int] | None = None


@dataclass
class TeamDeps:
    """Per-agent-run context passed into every tool call (PydanticAI deps)."""

    team: Team
    agent: AgentName
    ticket_id: int
    chain: list[str] = field(default_factory=list)  # e.g. ["boss", "inventory"]
    queue_task_id: int | None = None
