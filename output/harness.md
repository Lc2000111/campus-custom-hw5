# Campus Customs — Agent Harness

The complete harness for the HW5 multi-agent operations desk, covering:
- [Database files](#database-files)
- [Shop rules](#shop-rules)
- [Tables](#tables)
- [Open tickets](#open-tickets-and-how-they-link)
- [MCP tools](#all-mcp-tools-and-the-tables-they-use)
- [The five agents](#agent-team-problem-5)
- [API routes](#backend-routes-problem-7)
- [Dashboard](#dashboard-problem-8)
- [Final run results](#final-run-problem-9)
- [Safety](#safety)

**Layout:** `data/` (databases) · `mcp_server/` (FastMCP tools) · `backend/` (PydanticAI agents, FastAPI) · `frontend/` (React board) · `output/` (deliverables).

## Database files

| File | Role |
|---|---|
| `data/campus_customs.db` | **Original.** Never write to it. Used only to reset. |
| `data/campus_customs_new.db` | **Working copy.** MCP server and backend read and write here. |

Reset before every full ticket run:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

## Shop rules

1. **Today** is `desk.date_today` (currently `2026-08-31`). All overdue / due-soon math uses this date, not the system clock.
2. **Lead times** come from `vendors.lead_days`. ETA = `date_today + lead_days`.
3. **Vendor hold:** a vendor will not ship new product while it has any `invoices` row with `status = 'open'`.
4. **Human approval is required for every payment.** No agent may pay on its own.
5. **Record every payment:** insert a row into `payments` (with `approved_by`), lower `cash_accounts.balance`, and mark the invoice paid or move the lease's `next_due` forward.
6. **No negative balances:** the pay tool must refuse if `amount > cash_accounts.balance`.
7. **Cash only goes out.** No revenue is modeled, so the balance never goes up.
8. **No outbound contact:** don't email customers or call real vendors. Replies stay on the board as drafts.
9. **LLM:** every agent calls `gpt-5.6-luna` through Portkey, using `PORTKEY_API_KEY` from `.env`.

## Tables

### `desk`
Fields: `date_today`, `notes`
Why it matters: holds the shop's "today," which every agent needs for due dates, overdue checks, and ETAs.

### `tickets`
Fields: `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id` → `leases.id`, `invoice_id` → `invoices.id`, `status`, `notes`, `created_at`
Why it matters: the work queue. Each ticket's `type` decides which agent handles it, and its foreign keys point to the records that agent needs.

### `inventory`
Fields: `sku`, `size`, `name`, `qty`, `location` (PK: `sku` + `size`)
Why it matters: shows whether an order can be filled from stock or needs a reorder.

### `pricing`
Fields: `sku`, `unit_cost`, `list_price`
Why it matters: sets the margin. A discount must never price below `unit_cost`, and reorder cost = `qty × unit_cost`.

### `vendors`
Fields: `id`, `name`, `specialty`, `lead_days`
Why it matters: tells agents who can restock which kind of product and how long it takes.

### `leases`
Fields: `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`
Why it matters: rent is a fixed obligation with a due date, and it competes with vendor bills for the same cash.

### `cash_accounts`
Fields: `name`, `balance`, `date`
Why it matters: the only source of money. The pay tool checks it before every payment and refuses anything that would go negative.

### `payments`
Fields: `id`, `kind` (invoice / rent), `ref_id`, `amount`, `account`, `paid_at`, `approved_by`
Why it matters: the audit log. Each row records who approved the payment. It starts empty.

### `invoices`
Fields: `id`, `vendor_id` → `vendors.id`, `amount`, `due_date`, `status`, `description`
Why it matters: open invoices are debts, and any open invoice blocks that vendor from shipping.

### Working tables added by the MCP server
The original database doesn't have these. The server creates them in the working copy and recreates them after every reset.
- `payment_requests` (`id`, `kind`, `ref_id`, `vendor_id`, `sku`, `size`, `qty`, `amount`, `account`, `ticket_id`, `requested_by`, `reason`, `status`, `decided_by`, `decided_at`, `payment_id`, `eta`, `created_at`): money the agents prepared, waiting on a human signature.
- `drafts` (`id`, `ticket_id`, `author_agent`, `recipient`, `subject`, `body`, `status`, `created_at`): replies that stay on the board, never sent.
- `agent_queue` (`id`, `session_id`, `ticket_id`, `from_agent`, `to_agent`, `instruction`, `status`, `result`, `created_at`, `updated_at`): every delegation, so the agents can be tracked.

## Open tickets and how they link

Starting state: `date_today = 2026-08-31`, checking balance **$3,400.00**, `payments` empty.

### #101 — customer_order — Tauhid Zaman — Bulldog tee, S, qty 1
- `inventory` CC-TEE-WHITE / S: **qty 0** (out of stock).
- `invoice_id = 501` → Bulldog Print Co (vendor 1, `lead_days = 5`), **$840**, due 2026-08-28, `status = open`: **3 days overdue**. The description is "Rush reprint CC-TEE-WHITE S".
- Because invoice 501 is open, vendor 1 is on hold and will not ship.
- Path: pay 501 (needs human approval) → vendor ships → ETA 2026-08-31 + 5 = **2026-09-05** → draft the customer reply.

### #102 — rent_notice — Elm City Properties — rent due
- `lease_id = 1` → Chapel Street shop, **$2,400**, `next_due = 2026-09-02` (due in 2 days, not overdue yet).
- Path: pay rent (needs human approval) → record the payment → move `next_due` to 2026-10-02 → draft a reply to the landlord.

### #103 — price_override — Yale AI Club — 20 × CC-HOOD-NAVY, M, bulk discount
- `inventory` CC-HOOD-NAVY / M: **qty 8**, so 12 short (S 4, L 14, XL 6 aren't substitutes unless the customer agrees).
- `pricing`: unit cost $22, list price $58. Full price for 20 = $1,160, so any discount must stay above $22/unit.
- Restock comes from Bulldog Print Co (apparel), which is **blocked by invoice 501** and has a 5-day lead time.
- 12 more hoodies would cost 12 × $22 = **$264**.

### Cross-ticket cash constraint
| Item | Amount | Balance after |
|---|---|---|
| Start | — | $3,400 |
| Pay invoice 501 (#101) | $840 | $2,560 |
| Pay rent (#102) | $2,400 | $160 |
| Reorder 12 hoodies (#103) | $264 | **−$104: refused** |

Paying both obligations covers #101 and #102 but leaves $160, which can't fund the hoodie reorder. #103 needs a plan that doesn't spend more cash: fill 8 now and backorder the rest, or offer a partial order.

## MCP tools: the first three (Problem 3)

Server: `mcp_server/server.py` (FastMCP, reads `data/campus_customs_new.db`). These three tools are read-only. Each returns only database values, plus date math against `desk.date_today`.

### 1. `check_stock(sku, size, qty_requested)`
- **Reads:** `inventory` (qty for that sku/size and the other sizes), `pricing` (`unit_cost`, `list_price`)
- **Unlocks:** **#103**, Yale AI Club, 20 × CC-HOOD-NAVY size M with a bulk discount
- **Why:** #103 is a pricing request that depends on stock. The tool shows only 8 of the 20 M hoodies are in stock (12 short, with S 4 / L 14 / XL 6 as possible substitutes) and returns the $22 `unit_cost` as the floor below the $58 list price, so the pricing agent can offer a real partial-fill quote without discounting below cost. *(It also confirms #101's tee is 0 in size S.)*

### 2. `check_vendor_hold(vendor_id)`
- **Reads:** `vendors` (`name`, `specialty`, `lead_days`), `invoices` (this vendor's open rows), `desk` (`date_today`)
- **Unlocks:** **#101**, Tauhid Zaman's size S Bulldog tee
- **Why:** the tee is out of stock, and the only restock source, Bulldog Print Co (vendor 1), is on hold because invoice 501 ($840, due 2026-08-28) is 3 days overdue. The tool shows the hold, names the exact invoice that must be paid, and gives the ETA once it's cleared (2026-08-31 + 5 lead days = 2026-09-05), so the customer reply can quote a date from the database. *(It also shows #103's 12-hoodie restock is blocked by the same invoice.)*

### 3. `check_rent_due(lease_id)`
- **Reads:** `leases` (`monthly_rent`, `next_due`, `landlord`), `desk` (`date_today`), `cash_accounts` (`balance`)
- **Unlocks:** **#102**, the Elm City Properties rent notice
- **Why:** the ticket only says "rent due in 2 days." The tool checks it against lease 1 ($2,400 due 2026-09-02, 2 days from shop today) and confirms checking ($3,400) covers it with $1,000 left. That gives the human approver the full picture before any rent payment is made.

## Agent team (Problem 5)

Built with PydanticAI. Every agent uses **`gpt-5.6-luna` through Portkey** (`backend/llm.py`, key from `.env`, reasoning effort `low`).

| Agent | File | Prompt | Output | MCP tools it can call |
|---|---|---|---|---|
| **Boss** | `backend/agents/boss.py` | `backend/prompts/boss.md` | `TicketDecision` | `list_tickets`, `list_open_tickets`, `get_ticket`, `update_ticket`, `get_cash_position`, `list_payment_requests`, `list_drafts`, `list_queue` |
| **Inventory** | `backend/agents/inventory.py` | `backend/prompts/inventory.md` | `AgentReport` | `get_ticket`, `check_stock`, `list_vendors`, `check_vendor_hold` |
| **Accounting** | `backend/agents/accounting.py` | `backend/prompts/accounting.md` | `AgentReport` | `get_ticket`, `get_cash_position`, `check_margin`, `check_vendor_hold`, `request_payment`, `request_purchase_order`, `list_payment_requests` |
| **Facilities** | `backend/agents/facilities.py` | `backend/prompts/facilities.md` | `AgentReport` | `get_ticket`, `check_rent_due`, `save_draft`, `list_drafts` |
| **Customer Service** | `backend/agents/customer_service.py` | `backend/prompts/customer_service.md` | `AgentReport` | `get_ticket`, `save_draft`, `list_drafts` |

- **Roles:** Boss reads each ticket, delegates, and makes the final call (`update_ticket`). Inventory checks stock and shortfalls and matches products to vendors by `specialty`. Accounting watches cash, invoices, and margins and queues payments or POs for human approval. Facilities handles the lease, rent, and landlord draft. Customer Service drafts replies to customers.
- **Shared rules:** `backend/prompts/shop_rules.md` is appended to every agent's prompt.
- **Data types:** `backend/models.py` defines `AgentName`, `TicketStatus`, `AgentReport`, `TicketDecision`, `AuditEvent`, and `TeamDeps`.
- **Least privilege:** `backend/config.py` (`AGENT_TOOLS`) filters each agent's view of the MCP server. `approve_payment_request`, `enqueue_task`, and `update_task` are given to no agent, and an assertion fails at import if one is.
- **Full connectivity:** every agent has a `delegate(to_agent, task)` tool and can call any teammate. The only exception is an agent already in the current chain, which prevents ping-pong loops. Calls Boss makes in the same turn run in parallel.
- **Agent loop:** `backend/team.py` runs each agent with `agent.iter()`, step by step: user prompt → model request → model response (tool calls) → tool returns → … → end. Each delegation is queued on the MCP work queue (`enqueue_task` → `running` → `done`/`failed`) and its report goes back to the caller.
- **One source of shop facts:** agents and scripts reach the database only through the MCP server, launched from `.mcp.json` (`backend/mcp_client.py`). There is no second tools layer.

### How to run

```bash
.venv/bin/python -m backend.run --reset          # reset working copy, run all open tickets
.venv/bin/python -m backend.run --ticket 101     # one ticket on the current working copy
.venv/bin/python -m backend.queue_status         # track who asked whom to do what
.venv/bin/python -m backend.approve              # HUMAN: approve/reject queued payments
```

### Audit trail: `output/audit_trail.json`

This is an append-only JSON array. It is never wiped: each write reads the array, appends, and atomically replaces the file. One event is recorded per agent-loop step, plus `session_start/end`, `agent_start/end/error`, `delegation_refused`, and `human_decision`. Each event records:
- `ts`, `session_id`, `ticket_id`, `agent`, `agent_run_id`, `queue_task_id`, and `chain` (for example `["boss","facilities","accounting"]`)
- `step` and `node` (`user_prompt`, `model_request`, `model_response`, or `end`)
- `details`: tool calls with exact args, tool results (truncated at 4,000 characters), model text, the resolved model name, and the final output
- `usage`: cumulative requests, tool calls, and input/output/total tokens for the ticket
- On `agent_start`: who delegated, the instruction, and a `prompt_sha` fingerprint of the prompt version used

## Backend routes (Problem 7)

`backend/main.py` (FastAPI). Start it from `backend/` with `uvicorn main:app --reload --port 8000`, which serves the API at `http://localhost:8000`. Every shop fact goes through the MCP server, which is connected once at startup. CORS allows the Vite dashboard `http://localhost:5173` (and any other `localhost` / `127.0.0.1` port). The dashboard is in `frontend/` (Problem 8); start it with `npm run dev`.

- `GET /api/tickets`: all tickets, each with `state` = open or resolved (MCP `list_tickets`).
- `GET /api/tickets/{id}`: one ticket plus its linked invoice or lease, drafts, payment requests, and work-queue tasks.
- `POST /api/tickets/{id}/run`: starts the agent team on that ticket in the background and returns a `run_id` (202). Only one run at a time; a second returns 409. When the run finishes, the ticket is marked `resolved` (agent `desk`), with Boss's own call and any pending approvals written in the note.
- `GET /api/runs`: the runs since the backend started, plus the active one, so a reloaded page can resume watching.
- `GET /api/runs/{run_id}`: run status (running, done, or failed) and Boss's `TicketDecision` when finished.
- `GET /api/events?limit=50&ticket_id=&after=`: recent agent events from `audit_trail.json`: who started, what each agent said, which tools it called with which args, the tool results, and the final reports. Pass `after=<last_event_id>` to refresh incrementally. The response also includes `last_reset_event_id`, so the board hides runs from before a reset.
- `GET /api/payments?status=pending`: payment and purchase-order requests the agents queued, each with a readable `label` (for example "Invoice #501 · Bulldog Print Co"), the vendor name, and the ticket subject.
- `POST /api/payments/{id}/approve` `{"approved_by": "<name>"}`: **human click.** Approves and pays through MCP `approve_payment_request`. This is the only route that changes cash. It returns 409 if refused (insufficient funds or vendor on hold) and logs a `human_decision` to the audit trail.
- `POST /api/payments/{id}/reject` `{"approved_by": "<name>"}`: **human click.** Rejects the request; no money moves.
- `GET /api/cash`: current checking balance from `cash_accounts`, plus the pending total and the balance after pending.
- `POST /api/reset`: copies `campus_customs.db` over the working copy for a fresh run. Refused during a run; the audit trail is kept.
- `GET /api/health`: liveness check.

## Dashboard (Problem 8)

`frontend/` is built with React, Vite, and TypeScript. Start it with `npm run dev` from `frontend/`. It talks to `http://localhost:8000` (`VITE_API_URL` in `frontend/.env`) and binds to `127.0.0.1:5173`, or the next free port if that's taken; this session it ran on **5174** because another app holds 5173. Design rationale is in `output/design.md`.

| Area | What it shows | Route(s) |
|---|---|---|
| Header | Shop name and shop-today date; 3 numbered steps (Pick → Start → Sign; step 3 jumps to signing); **checking balance**, large, with "waiting for approval" and "if all approved" | `GET /api/cash` |
| Pink signature banner | Appears whenever anything needs a signature: count, total $, and a **Sign now** button | `GET /api/payments` |
| Ticket rail (left) | 3 paper stubs: id, subject, qty/size, open/working/resolved pill, "N payments need your signature," and a **RESOLVED** stamp | `GET /api/tickets` |
| Ticket hero | Key numbers as large tiles (qty, invoice $, rent $, days until due); **Start the agent team** button with a live timer | `GET /api/tickets/{id}`, `POST /api/tickets/{id}/run`, `GET /api/runs/{id}` |
| Agent floor | Boss at the head desk wired to 4 specialists. Each has its own colour and icon, a status pill (Idle/Thinking/Working/Done/Stuck), and a live speech bubble. Wires light up during hand-offs | `GET /api/events?after=` (polled every 1.2 s) |
| What each agent did | One card per agent: final words, tool chips, hand-offs, "Needs your OK." Drafts appear as paper notes marked "not sent" | `GET /api/events`, `GET /api/tickets/{id}` |
| **Sign here** tray (right; moves to the top on narrow screens) | Signature box styled like a signature line, cheques with amount and "checking after this," two-click Approve, Reject, and a "Signed & paid" ledger | `GET /api/payments`, `POST /api/payments/{id}/approve` and `/reject` |
| Desk chatter | Timeline of hand-offs, tool calls, final answers, and human signatures | `GET /api/events` |
| Footer | Backend URL, safety reminder, **Reset to original data** | `POST /api/reset` |

**Look:** white background, pink ink (#e6197a), soft shadows, and large monospace numbers. The user asked to switch from black to white and to make signing more prominent.

## All MCP tools and the tables they use

`mcp_server/server.py`: 19 tools, all `async`. Tables marked *(new)* are created in the working copy by the server. Resetting from the original removes them, and the server recreates them on start.

| # | Tool | Reads | Writes | Who can call it |
|---|---|---|---|---|
| 1 | `list_open_tickets()` | `tickets`, `desk` | — | Boss, run.py |
| 2 | `list_tickets()` | `tickets`, `desk` | — | Boss, `GET /api/tickets` (open and resolved) |
| 3 | `get_ticket(ticket_id)` | `tickets`, `invoices`, `vendors`, `leases`, `desk` | — | all agents |
| 4 | `update_ticket(ticket_id, status, note, agent)` | `tickets`, `desk` | `tickets` (status + dated note) | Boss |
| 5 | `check_stock(sku, size, qty_requested)` | `inventory`, `pricing` | — | Inventory |
| 6 | `list_vendors()` | `vendors`, `invoices`, `desk` | — | Inventory |
| 7 | `check_vendor_hold(vendor_id)` | `vendors`, `invoices`, `desk` | — | Inventory, Accounting |
| 8 | `check_rent_due(lease_id)` | `leases`, `desk`, `cash_accounts` | — | Facilities |
| 9 | `get_cash_position()` | `cash_accounts`, `invoices`, `vendors`, `leases`, `payment_requests`, `desk` | — | Boss, Accounting |
| 10 | `check_margin(sku, unit_price, qty)` | `pricing` | — | Accounting |
| 11 | `request_payment(kind, ref_id, ticket_id, requested_by, reason)` | `invoices` / `leases`, `cash_accounts` | `payment_requests` *(new)* | Accounting |
| 12 | `request_purchase_order(vendor_id, sku, size, qty, ticket_id, requested_by, reason)` | `vendors`, `invoices`, `inventory`, `pricing`, `cash_accounts`, `desk` | `payment_requests` *(new)* | Accounting |
| 13 | `list_payment_requests(status)` | `payment_requests` *(new)* | — | Boss, Accounting, approve.py |
| 14 | `approve_payment_request(request_id, approve, approved_by)` **HUMAN ONLY** | `payment_requests`, `invoices`, `leases`, `vendors`, `cash_accounts`, `desk` | `payments`, `cash_accounts`, `invoices` / `leases`, `payment_requests` | approve.py only |
| 15 | `save_draft(ticket_id, author_agent, recipient, subject, body)` | `tickets` | `drafts` *(new)* | Facilities, Customer Service |
| 16 | `list_drafts(ticket_id)` | `drafts` *(new)* | — | Boss, Facilities, Customer Service |
| 17 | `enqueue_task(session_id, ticket_id, from_agent, to_agent, instruction)` | — | `agent_queue` *(new)* | orchestrator only |
| 18 | `update_task(task_id, status, result)` | — | `agent_queue` *(new)* | orchestrator only |
| 19 | `list_queue(ticket_id, status)` | `agent_queue` *(new)* | — | Boss, queue_status.py |

- **Async tools and async queue:** every tool is an `async def`, and PydanticAI runs a model's parallel tool calls concurrently. `agent_queue` is the async work queue: each hand-off is a row moving `queued → running → done/failed` with its result, so you can track the agents live with `list_queue` / `backend.queue_status`.
- **New tables:** `payment_requests` holds money waiting on a human, `drafts` holds messages that stay on the board, and `agent_queue` holds delegations.
- **What a payment does:** an approved request inserts into `payments` (with `approved_by`), lowers `cash_accounts.balance`, and then updates the matching table: the invoice is marked `paid`, the lease's `next_due` moves forward one month, or a PO's `eta` is set to `date_today + lead_days`.

## Final run (Problem 9)

Run on 2026-10-10. Shop today is 2026-08-31.
- **Reset:** `POST /api/reset`, giving a clean working copy with checking **$3,400.00**, no payments, and all tickets open.
- **Runs:** tickets 101 → 102 → 103, one at a time through the board's run route.

An earlier attempt froze when one gateway call never returned. The fix was `MODEL_TIMEOUT_S = 90` plus 2 retries, then a reset and a rerun. The frozen attempt stays in the audit trail.

| Ticket | Agents (hand-offs) | Requests → human decision | Cash | Tokens |
|---|---|---|---|---|
| 101 | Boss → Inventory, Accounting, Customer Service (parallel); Customer Service → Inventory; Inventory → Accounting | #1 invoice 501 **$840**, approved; #2 PO 1 × tee S **$8**, approved | −$848 | 46,990 |
| 102 | Boss → Facilities, Accounting (parallel); Facilities → Accounting | #3 rent lease 1 **$2,400**, approved | −$2,400 | 25,429 |
| 103 | Boss → Inventory, Accounting, Customer Service (parallel) | none (8/20 in stock, no affordable restock, floor $22) | $0 | 25,570 |

- **Ending checking: $152.00** = `cash_accounts.balance` in `data/campus_customs_new.db` ✓. The `payments` table has 3 rows totalling $3,248, all `approved_by = Josh Liang`.
- **Side effects of the payments:**
  - Invoice 501 → `paid`.
  - Lease 1 `next_due` → 2026-10-02.
  - PO ETA → 2026-09-05.
- **Drafts on the board, not sent:** #1 to Tauhid, #2 to Elm City Properties, #3 to Yale AI Club.
- **Where the details are:**
  - `output/desk_tickets.html` (Expected vs Actual, Cash tab)
  - `output/resolved_tickets.json`
  - `output/resolved_board.html` (board screenshots)
  - `output/audit_trail.json` (every step)

## Safety

### Guardrails for real customers and real money
1. **A human approves all spending.** Agents can only *queue* payments or POs. Moving cash is a separate human-only tool, never handed to an agent, and it requires a named approver; agent names are rejected. A real business would add identity-backed sign-in, two-person approval above a threshold, and a daily spend cap.
2. **Amounts come from the database, never from the model.** `request_payment` reads the invoice or rent amount, and `request_purchase_order` computes `qty × unit_cost`. The model can't make up a number.
3. **Hard money checks in code, not prompts.** The balance can't go negative (an atomic conditional UPDATE), a request can't be paid twice, a PO can't be paid while the vendor is on hold, and a bill that's no longer open can't be paid.
4. **No outbound contact.** There's no email or phone tool at all. Drafts go to a `drafts` table with `status = 'draft'`, and a human reviews and sends them.
5. **Least-privilege tools.** Each agent sees only the MCP tools its role needs. Customer Service can't touch money, and Inventory can't queue spending.
6. **No made-up facts.** Every tool returns an `error` instead of guessing, prompts require citing the tool behind each fact, and `check_margin` flags any price below cost.
7. **Full audit and reset.** Every step, tool argument, result, and human decision is appended to `audit_trail.json` with a prompt fingerprint. The original database is never written, so it's always possible to reset.
8. **Human signature on the board.** Approve takes two clicks ("Approve" → "Yes, pay $X") and requires a typed name, which is stored as `approved_by`. The cheque shows "checking after this" before you sign and warns if the payment would be refused. A ticket marked **resolved** never hides an unpaid request: pending signatures stay on the stub and in the pink banner.
9. **The backend is local only.** CORS allows only `localhost` / `127.0.0.1` (the Vite page). Only one agent run can happen at a time, and reset is refused during a run.
10. **Recommended for production:** human review of discounts and refunds, redaction of customer personal data in logs, alerts on refused payments, and a kill switch that pauses the queue.

### Limits that keep token use in check
- **Per-ticket budget** shared by every agent in the chain (`TICKET_USAGE_LIMITS`): 40 model requests, 60 tool calls, and 200,000 total tokens. Going over it stops the run cleanly and logs `agent_error`.
- **Delegation caps:** depth 3 (Boss → specialist → specialist), at most 8 delegations per ticket, no delegating to yourself or back up the chain, and duplicate payment requests are ignored.
- **Cheap model settings:** reasoning effort `low`, 1 retry on bad tool arguments or output, and compact structured outputs (`AgentReport` / `TicketDecision`).
- **Small context:** each agent gets only its own prompt plus the shared rules and its own tools. Boss passes the confirmed facts down so specialists don't re-query, and the audit log truncates large tool results.
- **Per-call timeout:** each model call times out after 90 s with 2 retries (`MODEL_TIMEOUT_S`), so a stalled gateway call can't freeze a run or keep holding tokens.
- **Final run on 2026-10-10:** 47k, 25k, and 26k tokens for 101, 102, and 103 (each under 25% of the 200k per-ticket budget).

## Open questions
- Invoice 501 is described as "Rush reprint CC-TEE-WHITE S." In the final run the agents *also* bought one new tee ($8 PO). The database can't tell us whether the reprint already covered it, so a human may want to check for double-ordering.
- Ticket 103's bulk price (at or above $22) and whether to restock 12 more hoodies ($264, more than the $152 left) are still human decisions.
- Invoice status after payment: the system uses `paid`.
