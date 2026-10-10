# Campus Customs — Multi-Agent Operations Desk (MGT 409, HW5)

A five-agent team handles a campus apparel shop's open tickets. Boss, Inventory, Accounting, Facilities and Customer Service are built with **PydanticAI** on **gpt-5.6-luna through Portkey**. Every shop fact comes from a **FastMCP** server over SQLite. A **FastAPI** backend runs the agents, and a **React + Vite + TypeScript** board shows them working and lets a human sign each payment.

Agents can only *prepare* money. Cash moves only when a human clicks **Approve** on the board. A payment that would make the balance negative is refused, and nothing is ever emailed: replies stay on the board as drafts.

## File layout

```
AI_prompts.md          log of every prompt typed while building this (Problems 1–11)
requirements.txt       Python dependencies
.env.example           copy to .env and add your PORTKEY_API_KEY (.env is git-ignored)
.gitignore
.mcp.json              MCP connection used by Claude Code and by the backend
README.md
data/
  campus_customs.db      ORIGINAL shop database (never written to; used for resets)
  campus_customs_new.db  WORKING copy the MCP server reads and writes
                         (committed in its graded state: all 3 tickets resolved, checking $152.00)
mcp_server/            FastMCP server (19 tools) + readme + smoke test
backend/               PydanticAI agents (agents/, prompts/, models.py, team.py) and the FastAPI app (main.py)
frontend/              React + Vite + TypeScript board
output/                harness.md, desk_tickets.html, design.md, resolved_tickets.json,
                       resolved_board.html, audit_trail.json, mcp_smoke.json, github_url.txt, screenshots/
```

## 1 · One-time setup

You need Python 3.12+ and Node 20+.

```bash
git clone https://github.com/Lc2000111/campus-custom-hw5.git && cd campus-custom-hw5

# Python
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Your key: create .env from the template and paste your own Portkey key
cp .env.example .env

# Front end
cd frontend && npm install && cd ..
```

## 2 · Clean run: copy the original DB to the working copy

`data/campus_customs_new.db` is the working copy that everything writes to. To start fresh, copy the original over it:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

The board's **Reset to original data** button (`POST /api/reset`) and `python -m backend.run --reset` do the same copy. Afterwards checking is back to **$3,400.00** and tickets 101, 102 and 103 are open again. The MCP server recreates its working tables (`payment_requests`, `drafts`, `agent_queue`) automatically. `output/audit_trail.json` is append-only and is **never** wiped.

## 3 · Start the MCP server

The backend starts the MCP server for you, as a child process launched from `.mcp.json`. To run it on its own, for example to inspect it or to connect Claude Code through `.mcp.json`, run from the repo root:

```bash
.venv/bin/python mcp_server/server.py
```

To test the original three tools over MCP, run the smoke test below. It expects a clean database, so reset first, and note that it rewrites `output/mcp_smoke.json`.

```bash
.venv/bin/python mcp_server/smoke_test.py
```

See `mcp_server/readme.md` for all 19 tools and the tables each one uses.

## 4 · Start the FastAPI backend

Start it from the `backend/` folder:

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

The API runs at http://localhost:8000. The routes are listed in `output/harness.md`, for example `GET /api/tickets`, `POST /api/tickets/{id}/run`, `GET /api/events`, `POST /api/payments/{id}/approve`, `GET /api/cash` and `POST /api/reset`.

## 5 · Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

This opens **http://127.0.0.1:5173**. If 5173 is busy, Vite picks the next free port; the backend allows any localhost port. Then:

1. Pick a ticket.
2. Click **Start the agent team**.
3. Watch the agents in the live chatter.
4. Type your name in **Your signature** and approve or reject each payment in **Sign here**. The pink banner jumps you there.

## 6 · Reset the DB before a full three-ticket run

**Always reset before running all three tickets**, so the cash math starts from $3,400.00. Then run 101 → 102 → 103 on the board, or from the command line:

```bash
.venv/bin/python -m backend.run --reset      # resets, then runs every open ticket
.venv/bin/python -m backend.approve          # human sign-off in the terminal (alternative to the board)
.venv/bin/python -m backend.queue_status     # who asked whom to do what
```

The committed working copy has the graded run: three human-approved payments of $840 (invoice 501), $8 (one size S tee) and $2,400 (rent), taking checking from $3,400.00 to **$152.00**. `output/desk_tickets.html` (Cash tab) and `output/resolved_tickets.json` match it. Resetting replaces that state.

## Shop rules the agents follow

- `desk.date_today` (2026-08-31) is "today."
- Vendor lead times come from `vendors.lead_days`.
- A vendor won't ship while it has an open invoice.
- Every payment needs human approval, is recorded in `payments`, and updates `cash_accounts` and the invoice or lease.
- The pay tool refuses negative balances.
- Cash only goes out.
- No customer or vendor is contacted.

All agents use `gpt-5.6-luna` via Portkey (`PORTKEY_API_KEY`).

## Where to read more

| File | What's in it |
|---|---|
| `output/harness.md` | Tables, all MCP tools, the five agents, API routes, dashboard, final run and safety rules |
| `output/desk_tickets.html` | Expected vs Actual per ticket, Cash tab, Reflection (double-click to open) |
| `output/resolved_board.html` | Screenshots of the board for each resolved ticket |
| `output/design.md` | Why the board looks and works the way it does |
| `output/audit_trail.json` | Every agent-loop step, tool call and human decision |
| `AI_prompts.md` | The prompts used to build all of this |
