"""Boss agent: Reads each ticket, delegates to specialists, and makes the final call.

Prompt: backend/prompts/boss.md (+ shop_rules.md)
MCP tools: see AGENT_TOOLS["boss"] in backend/config.py
"""

from backend.agents.base import build_agent
from backend.models import TicketDecision

NAME = "boss"


def build(model, mcp):
    return build_agent(NAME, TicketDecision, model, mcp)
