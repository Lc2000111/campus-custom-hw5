"""Smoke-test the Campus Customs MCP server over stdio and save evidence.

Launches the server exactly as .mcp.json describes, calls each tool through
the MCP protocol, then re-reads the same values straight from
data/campus_customs_new.db with SQL and records whether they match.

Run from hw5/:  .venv/bin/python mcp_server/smoke_test.py
"""

import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"
OUT_PATH = ROOT / "output" / "mcp_smoke.json"

TESTS = [
    {
        "ticket": 103,
        "prompt": "Ticket 103: Yale AI Club wants 20 navy hoodies in size M. "
                  "How many can we fill from stock, and what is the lowest per-unit price we could discount to?",
        "tool": "check_stock",
        "args": {"sku": "CC-HOOD-NAVY", "size": "M", "qty_requested": 20},
        "sql": "SELECT i.qty AS qty_on_hand, p.unit_cost, p.list_price FROM inventory i "
               "JOIN pricing p ON p.sku = i.sku WHERE i.sku = 'CC-HOOD-NAVY' AND i.size = 'M'",
        "compare": lambda out: {
            "qty_on_hand": out["qty_on_hand"],
            "unit_cost": out["pricing"]["unit_cost"],
            "list_price": out["pricing"]["list_price"],
        },
    },
    {
        "ticket": 101,
        "prompt": "Ticket 101: Tauhid needs a size S Bulldog tee. Will Bulldog Print Co (vendor 1) ship a restock, "
                  "and if not, what is blocking it and when could it arrive?",
        "tool": "check_vendor_hold",
        "args": {"vendor_id": 1},
        "sql": "SELECT v.name, v.lead_days, i.id AS invoice_id, i.amount, i.due_date, i.status, d.date_today "
               "FROM vendors v JOIN invoices i ON i.vendor_id = v.id AND i.status = 'open' "
               "CROSS JOIN desk d WHERE v.id = 1",
        "compare": lambda out: {
            "name": out["name"],
            "lead_days": out["lead_days"],
            "invoice_id": out["open_invoices"][0]["invoice_id"],
            "amount": out["open_invoices"][0]["amount"],
            "due_date": out["open_invoices"][0]["due_date"],
            "status": "open" if out["on_hold"] else "none",
            "date_today": out["shop_today"],
        },
    },
    {
        "ticket": 102,
        "prompt": "Ticket 102: Elm City Properties says rent is due in 2 days. "
                  "How much is due, on what date, and can our checking account cover it?",
        "tool": "check_rent_due",
        "args": {"lease_id": 1},
        "sql": "SELECT l.landlord, l.monthly_rent, l.next_due, c.balance, d.date_today "
               "FROM leases l CROSS JOIN cash_accounts c CROSS JOIN desk d "
               "WHERE l.id = 1 AND c.name = 'checking'",
        "compare": lambda out: {
            "landlord": out["landlord"],
            "monthly_rent": out["monthly_rent"],
            "next_due": out["next_due"],
            "balance": out["cash_accounts"][0]["balance"],
            "date_today": out["shop_today"],
        },
    },
]


async def main() -> None:
    config = json.loads((ROOT / ".mcp.json").read_text())
    for server in config["mcpServers"].values():  # .mcp.json paths are relative to the project root
        server["command"] = str(ROOT / server["command"]) if "/" in server["command"] else server["command"]
        server["args"] = [str(ROOT / a) if a.endswith(".py") else a for a in server["args"]]
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    results = []
    async with Client(config) as client:
        listed = [t.name for t in await client.list_tools()]
        for t in TESTS:
            response = await client.call_tool(t["tool"], t["args"])
            output = response.data
            db_row = dict(conn.execute(t["sql"]).fetchone())
            tool_values = t["compare"](output)
            results.append({
                "ticket": t["ticket"],
                "prompt": t["prompt"],
                "tool": t["tool"],
                "arguments": t["args"],
                "tool_output": output,
                "db_check": {
                    "sql": t["sql"],
                    "db_values": db_row,
                    "tool_values": tool_values,
                    "matches_db": tool_values == db_row,
                },
            })
    conn.close()

    evidence = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "database": "data/campus_customs_new.db",
        "transport": "stdio, launched from .mcp.json (server 'campus-customs')",
        "tools_listed_by_server": listed,
        "all_match_db": all(r["db_check"]["matches_db"] for r in results),
        "tests": results,
    }
    OUT_PATH.write_text(json.dumps(evidence, indent=2) + "\n")
    for r in results:
        print(f"#{r['ticket']} {r['tool']}: matches_db={r['db_check']['matches_db']}")
    print(f"all_match_db={evidence['all_match_db']} -> {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
