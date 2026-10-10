"""Track the agents: print the MCP work queue (who asked whom to do what).

    .venv/bin/python -m backend.queue_status [--ticket 101]
"""

import argparse
import asyncio

from backend.mcp_client import build_mcp_toolset


async def main(ticket_id: int | None) -> None:
    mcp = build_mcp_toolset()
    async with mcp:
        tasks = (await mcp.direct_call_tool("list_queue", {"ticket_id": ticket_id}))["tasks"]
    print(f"{'id':>4}  {'ticket':>6}  {'from':<16} {'to':<16} {'status':<8} instruction")
    for t in tasks:
        print(f"{t['id']:>4}  {t['ticket_id']:>6}  {t['from_agent']:<16} {t['to_agent']:<16} "
              f"{t['status']:<8} {t['instruction'][:70]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticket", type=int)
    asyncio.run(main(parser.parse_args().ticket))
