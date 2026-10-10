# Campus Customs MCP Server

**What it's for:** This is the single tool layer for every HW5 agent (Boss, Inventory, Accounting, Facilities, and Customer Service). Agents never query SQLite directly. They call these tools, so every shop fact comes from the database and nothing is made up. Built with [FastMCP](https://gofastmcp.com). All tools are `async`.

**Database:** `data/campus_customs_new.db` is the working copy. The original `data/campus_customs.db` is never opened, so you can reset with:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

All dates are measured against `desk.date_today`, the shop's "today," not the system clock. On start, the server adds three working tables if they're missing: `payment_requests`, `drafts`, and `agent_queue`.

## Tools (19)

| Tool | Tables | Purpose |
|---|---|---|
| `list_tickets()` | tickets, desk | Every ticket, open or resolved |
| `list_open_tickets()` | tickets, desk | Every ticket not yet resolved |
| `get_ticket(ticket_id)` | tickets, invoices, vendors, leases, desk | A ticket plus its linked invoice or lease |
| `update_ticket(ticket_id, status, note, agent)` | tickets | Set status and append a dated note |
| `check_stock(sku, size, qty_requested)` | inventory, pricing | On hand, shortfall, other sizes, discount floor |
| `list_vendors()` | vendors, invoices, desk | Specialty, lead days, on hold, ETA |
| `check_vendor_hold(vendor_id)` | vendors, invoices, desk | Open invoices blocking a vendor, and the ETA once cleared |
| `check_rent_due(lease_id)` | leases, desk, cash_accounts | Rent amount, days until due, whether cash covers it |
| `get_cash_position()` | cash_accounts, invoices, vendors, leases, payment_requests, desk | Cash compared with open bills, rent, and pending requests |
| `check_margin(sku, unit_price, qty)` | pricing | Margin on a proposed price, flags anything below cost |
| `request_payment(kind, ref_id, ticket_id, requested_by, reason)` | invoices / leases, cash_accounts → **payment_requests** | Queue an invoice or rent payment for a human. The amount comes from the database. |
| `request_purchase_order(vendor_id, sku, size, qty, ticket_id, requested_by, reason)` | vendors, invoices, inventory, pricing, cash_accounts → **payment_requests** | Queue a restock PO for a human. Cost = qty × unit_cost. |
| `list_payment_requests(status)` | payment_requests | Pending, paid, or rejected requests |
| `approve_payment_request(request_id, approve, approved_by)` **HUMAN ONLY** | payment_requests → **payments, cash_accounts, invoices / leases** | The only tool that moves cash. Refuses negative balances, double payment, and vendors on hold. |
| `save_draft(ticket_id, author_agent, recipient, subject, body)` | tickets → **drafts** | Save a message on the board. Never sends. |
| `list_drafts(ticket_id)` | drafts | Drafts on the board |
| `enqueue_task(session_id, ticket_id, from_agent, to_agent, instruction)` | → **agent_queue** | Orchestrator only: record a delegation |
| `update_task(task_id, status, result)` | → **agent_queue** | Orchestrator only: queued → running → done or failed |
| `list_queue(ticket_id, status)` | agent_queue | Track who is working on what |

If a record doesn't exist, the tool returns an `error` key and doesn't guess. `approve_payment_request`, `enqueue_task`, and `update_task` are never given to any agent (see `backend/config.py`). Payments are approved only by a human, either through `backend/approve.py` or the dashboard's approve button (`POST /api/payments/{id}/approve`).

## Run

From `hw5/`:

```bash
.venv/bin/python mcp_server/server.py
```

Claude Code and the agent backend both connect through `hw5/.mcp.json` (server name `campus-customs`). To test the original three tools over MCP and save the evidence to `output/mcp_smoke.json`, run:

```bash
.venv/bin/python mcp_server/smoke_test.py
```
