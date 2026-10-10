"""Shared agent factory: prompt + model + least-privilege MCP tools + delegate."""

from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model
from pydantic_ai.toolsets import FunctionToolset

from backend.config import AGENT_RETRIES, AGENT_TOOLS, PROMPTS_DIR
from backend.models import AgentName, TeamDeps


async def delegate(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> dict:
    """Hand a sub-task to a teammate and wait for their report.

    Any agent can delegate to any other agent that is not already in the
    current chain. Include the ticket id and the facts the teammate needs.
    """
    return await ctx.deps.team.delegate(ctx, to_agent, task)


delegation_toolset = FunctionToolset([delegate])


def load_instructions(name: str) -> str:
    role = (PROMPTS_DIR / f"{name}.md").read_text()
    rules = (PROMPTS_DIR / "shop_rules.md").read_text()
    return f"{role}\n\n{rules}"


def build_agent(name: AgentName, output_type: type, model: Model, mcp: MCPToolset) -> Agent:
    allowed = AGENT_TOOLS[name]
    shop_tools = mcp.filtered(lambda ctx, tool_def: tool_def.name in allowed)
    return Agent(
        model,
        name=name,
        deps_type=TeamDeps,
        output_type=output_type,
        instructions=load_instructions(name),
        toolsets=[shop_tools, delegation_toolset],
        retries=AGENT_RETRIES,
    )
