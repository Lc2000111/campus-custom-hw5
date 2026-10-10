"""Accounting agent: Watches cash and invoices, checks margins, queues payments / POs for human approval.

Prompt: backend/prompts/accounting.md (+ shop_rules.md)
MCP tools: see AGENT_TOOLS["accounting"] in backend/config.py
"""

from backend.agents.base import build_agent
from backend.models import AgentReport

NAME = "accounting"


def build(model, mcp):
    return build_agent(NAME, AgentReport, model, mcp)
