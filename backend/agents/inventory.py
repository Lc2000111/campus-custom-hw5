"""Inventory agent: Checks stock by SKU and size, spots shortfalls, finds the vendor that can restock.

Prompt: backend/prompts/inventory.md (+ shop_rules.md)
MCP tools: see AGENT_TOOLS["inventory"] in backend/config.py
"""

from backend.agents.base import build_agent
from backend.models import AgentReport

NAME = "inventory"


def build(model, mcp):
    return build_agent(NAME, AgentReport, model, mcp)
