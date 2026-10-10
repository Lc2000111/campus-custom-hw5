"""The five Campus Customs agents."""

from backend.agents import accounting, boss, customer_service, facilities, inventory

ROLES = {m.NAME: m for m in (boss, inventory, accounting, facilities, customer_service)}


def build_all(model, mcp) -> dict:
    return {name: module.build(model, mcp) for name, module in ROLES.items()}
