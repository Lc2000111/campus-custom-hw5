"""Customer Service agent: Drafts messages to customers (saved on the board, never sent).

Prompt: backend/prompts/customer_service.md (+ shop_rules.md)
MCP tools: see AGENT_TOOLS["customer_service"] in backend/config.py
"""

from backend.agents.base import build_agent
from backend.models import AgentReport

NAME = "customer_service"


def build(model, mcp):
    return build_agent(NAME, AgentReport, model, mcp)
