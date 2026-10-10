"""Connect to the Campus Customs MCP server described in .mcp.json.

This is the only path to shop data: agents and scripts call MCP tools, never
SQLite directly.
"""

import json

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from backend.config import MCP_CONFIG, MCP_SERVER_NAME, ROOT


def _resolve(path: str) -> str:
    """Paths in .mcp.json are relative to the project root (so the repo works after cloning)."""
    return str(ROOT / path) if "/" in path and not path.startswith("/") else path


def build_mcp_toolset() -> MCPToolset:
    server = json.loads(MCP_CONFIG.read_text())["mcpServers"][MCP_SERVER_NAME]
    transport = StdioTransport(
        command=_resolve(server["command"]),
        args=[_resolve(a) for a in server["args"]],
        cwd=str(ROOT),
    )
    return MCPToolset(Client(transport), id=MCP_SERVER_NAME, max_retries=1)
