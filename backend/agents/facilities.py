"""Facilities agent: Handles the shop space: leases, rent, landlord replies.

Prompt: backend/prompts/facilities.md (+ shop_rules.md)
MCP tools: see AGENT_TOOLS["facilities"] in backend/config.py
"""

from backend.agents.base import build_agent
from backend.models import AgentReport

NAME = "facilities"


def build(model, mcp):
    return build_agent(NAME, AgentReport, model, mcp)
