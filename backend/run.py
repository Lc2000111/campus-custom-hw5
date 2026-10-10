"""Run the Campus Customs agent team over the open tickets.

    .venv/bin/python -m backend.run --reset            # fresh copy, all open tickets
    .venv/bin/python -m backend.run --ticket 101       # one ticket, current working copy

No money moves during a run: payments / POs are only queued. Approve them
afterwards, as a human, with  .venv/bin/python -m backend.approve
"""

import argparse
import asyncio
import json
import shutil
from datetime import datetime
from uuid import uuid4

from backend.audit import AuditLog
from backend.config import ORIGINAL_DB, WORKING_DB
from backend.llm import build_model
from backend.mcp_client import build_mcp_toolset
from backend.team import Team


def reset_working_db() -> None:
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    print(f"Reset {WORKING_DB.name} from {ORIGINAL_DB.name}")


async def main(ticket_ids: list[int] | None, was_reset: bool = False) -> None:
    session_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:4]
    audit = AuditLog(session_id)
    if was_reset:
        audit.append("database_reset", details={"source": "cli"})
    mcp = build_mcp_toolset()

    async with mcp:
        team = Team(session_id, mcp, build_model(), audit)
        if not ticket_ids:
            ticket_ids = [t["id"] for t in (await team.call("list_open_tickets", {}))["tickets"]]
        audit.append("session_start", details={"tickets": ticket_ids})
        print(f"Session {session_id}: tickets {ticket_ids}")

        decisions = {}
        for ticket_id in ticket_ids:
            print(f"\n=== Ticket {ticket_id} ===")
            decisions[ticket_id] = await team.run_ticket(ticket_id)
            print(json.dumps(decisions[ticket_id], indent=2))

        pending = (await team.call("list_payment_requests", {"status": "pending"}))["requests"]
        audit.append("session_end", details={"decisions": decisions, "pending_request_ids": [p["id"] for p in pending]})

    print("\n=== Waiting on a human ===")
    for p in pending:
        what = f"{p['kind']} ref {p['ref_id']}" if p["kind"] != "purchase_order" else \
            f"PO {p['qty']} x {p['sku']} {p['size']}"
        print(f"  request #{p['id']}: {what}  ${p['amount']:.2f}  (ticket {p['ticket_id']})")
    if pending:
        print("Approve or reject:  .venv/bin/python -m backend.approve")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="copy campus_customs.db over the working copy first")
    parser.add_argument("--ticket", type=int, action="append", help="ticket id (repeatable); default: all open")
    args = parser.parse_args()
    if args.reset:
        reset_working_db()
    asyncio.run(main(args.ticket, args.reset))
