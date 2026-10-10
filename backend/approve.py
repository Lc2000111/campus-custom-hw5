"""Human approval desk: the ONLY way money moves.

    .venv/bin/python -m backend.approve

Lists pending payment / purchase-order requests the agents queued, shows the
cash position, and asks you to approve or reject each one. Approval goes
through the MCP tool `approve_payment_request`, which refuses anything that
would make the balance negative. Must be run in an interactive terminal.
"""

import asyncio
import sys
from datetime import datetime
from uuid import uuid4

from backend.audit import AuditLog
from backend.mcp_client import build_mcp_toolset


async def main() -> None:
    if not sys.stdin.isatty():
        sys.exit("approve.py must be run by a human in an interactive terminal.")
    approver = input("Your name (recorded as approved_by): ").strip()
    if not approver:
        sys.exit("A name is required.")

    audit = AuditLog("approve-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:4])
    mcp = build_mcp_toolset()
    async with mcp:
        pending = (await mcp.direct_call_tool("list_payment_requests", {"status": "pending"}))["requests"]
        if not pending:
            print("No pending requests.")
            return
        for req in pending:
            cash = await mcp.direct_call_tool("get_cash_position", {})
            print(f"\nCash on hand: ${cash['total_cash']:.2f}")
            print(f"Request #{req['id']}  {req['kind']}  ${req['amount']:.2f}  ticket {req['ticket_id']}")
            if req["kind"] == "purchase_order":
                print(f"  PO: {req['qty']} x {req['sku']} size {req['size']} from vendor {req['vendor_id']}")
            else:
                print(f"  ref_id: {req['ref_id']}")
            print(f"  requested by {req['requested_by']}: {req['reason']}")

            answer = input("Approve and pay? [y = approve / n = reject / Enter = skip]: ").strip().lower()
            if answer not in ("y", "n"):
                print("  skipped")
                continue
            result = await mcp.direct_call_tool("approve_payment_request", {
                "request_id": req["id"], "approve": answer == "y", "approved_by": approver,
            })
            print(f"  -> {result}")
            audit.append("human_decision", ticket_id=req["ticket_id"], agent="human", details={
                "request_id": req["id"], "decision": "approve" if answer == "y" else "reject",
                "approved_by": approver, "result": result,
            })


if __name__ == "__main__":
    asyncio.run(main())
