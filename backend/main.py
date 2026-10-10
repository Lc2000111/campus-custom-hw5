"""Campus Customs backend API for the React dashboard.

Start from the backend/ folder:
    uvicorn main:app --reload --port 8000

Every shop fact goes through the MCP server (one connection opened at
startup); agent events come from output/audit_trail.json. Agents only queue
payments; the approve route below is the human click that moves cash.
"""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `backend.*` imports work from backend/

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.audit import AuditLog  # noqa: E402
from backend.config import AUDIT_PATH  # noqa: E402
from backend.llm import build_model  # noqa: E402
from backend.mcp_client import build_mcp_toolset  # noqa: E402
from backend.run import reset_working_db  # noqa: E402
from backend.team import Team  # noqa: E402

state: dict = {"mcp": None, "model": None, "runs": {}, "active_run": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    mcp = build_mcp_toolset()
    async with mcp:
        state["mcp"] = mcp
        state["model"] = build_model()
        yield


app = FastAPI(title="Campus Customs API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],     # the Vite dashboard
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",       # other local ports only
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp_call(tool: str, args: dict | None = None) -> dict:
    result = await state["mcp"].direct_call_tool(tool, args or {})
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


def new_session_id(prefix: str = "") -> str:
    return prefix + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:4]


# ------------------------------------------------------------------ tickets

@app.get("/api/tickets")
async def list_tickets():
    """All tickets, each marked open or resolved."""
    data = await mcp_call("list_tickets")
    for t in data["tickets"]:
        t["state"] = "resolved" if t["status"] == "resolved" else "open"
    return data


@app.get("/api/tickets/{ticket_id}")
async def ticket_detail(ticket_id: int):
    """One ticket with its drafts, payment requests and work-queue tasks."""
    ticket = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    drafts = (await mcp_call("list_drafts", {"ticket_id": ticket_id}))["drafts"]
    requests = (await mcp_call("list_payment_requests", {"status": "all"}))["requests"]
    queue = (await mcp_call("list_queue", {"ticket_id": ticket_id}))["tasks"]
    return {
        **ticket,
        "drafts": drafts,
        "payment_requests": [r for r in requests if r["ticket_id"] == ticket_id],
        "queue": queue,
    }


# ------------------------------------------------------------------ agent runs

async def _run_ticket(run_id: str, ticket_id: int) -> None:
    run = state["runs"][run_id]
    audit = AuditLog(run["session_id"])
    audit.append("session_start", details={"tickets": [ticket_id], "source": "api"})
    try:
        team = Team(run["session_id"], state["mcp"], state["model"], audit)
        decision = await team.run_ticket(ticket_id)
        run["decision"] = decision
        run["status"] = "failed" if "error" in decision else "done"
        if run["status"] == "done":
            # The run is finished: the desk marks the ticket resolved. Boss's own call and anything
            # still waiting on a human stay visible in the note and in /api/payments.
            waiting = decision.get("payment_request_ids") or []
            await mcp_call("update_ticket", {
                "ticket_id": ticket_id, "status": "resolved", "agent": "desk",
                "note": f"Agent run {run_id} finished. Boss's call: {decision.get('ticket_status')}. "
                        f"Waiting on human approval: {waiting or 'none'}.",
            })
    except Exception as exc:
        run["status"], run["error"] = "failed", f"{type(exc).__name__}: {exc}"
    finally:
        run["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        audit.append("session_end", details={"run_id": run_id, "status": run["status"],
                                             "decisions": {ticket_id: run.get("decision")}})
        state["active_run"] = None


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int):
    """Start the agent team on one ticket (runs in the background; poll /api/runs/{run_id} and /api/events)."""
    await mcp_call("get_ticket", {"ticket_id": ticket_id})  # 404 if unknown
    if state["active_run"]:
        raise HTTPException(409, f"Run {state['active_run']} is still in progress; one run at a time.")
    run_id = uuid4().hex[:8]
    state["runs"][run_id] = {
        "run_id": run_id, "ticket_id": ticket_id, "status": "running",
        "session_id": new_session_id(), "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    state["active_run"] = run_id
    asyncio.create_task(_run_ticket(run_id, ticket_id))
    return state["runs"][run_id]


@app.get("/api/runs")
async def list_runs():
    """Runs started since the backend booted, plus the one in progress (if any)."""
    return {"active_run": state["active_run"], "runs": list(state["runs"].values())}


@app.get("/api/runs/{run_id}")
async def run_status(run_id: str):
    """Status of a run started by POST /api/tickets/{id}/run, with Boss's decision when done."""
    if run_id not in state["runs"]:
        raise HTTPException(404, f"Run {run_id} not found.")
    return state["runs"][run_id]


# ------------------------------------------------------------------ events

def _flatten(index: int, e: dict) -> list[dict]:
    """Turn one audit event into board-friendly rows: who said what, which tool was used."""
    base = {"event_id": index, "ts": e["ts"], "session_id": e["session_id"],
            "ticket_id": e.get("ticket_id"), "agent": e.get("agent"), "chain": e.get("chain", [])}
    d = e.get("details", {})
    kind = e["event"]
    if kind == "agent_start":
        return [{**base, "type": "started", "text": d.get("instruction"), "from_agent": d.get("from_agent")}]
    if kind == "agent_end":
        out = d.get("output", {})
        return [{**base, "type": "finished", "text": out.get("final_decision") or out.get("summary"), "output": out}]
    if kind == "agent_error":
        return [{**base, "type": "error", "text": d.get("error")}]
    if kind == "delegation_refused":
        return [{**base, "type": "refused", "text": f"-> {d.get('to_agent')}: {d.get('reason')}"}]
    if kind == "human_decision":
        return [{**base, "type": "human_decision", "text": json.dumps(d)}]
    if kind == "agent_step" and e.get("node") == "model_response":
        rows = []
        for p in d.get("parts", []):
            if p["kind"] == "tool-call" and p["tool"] == "final_result":
                continue  # structured output, shown on "finished"
            if p["kind"] == "tool-call":
                rows.append({**base, "type": "tool_call", "tool": p["tool"], "args": p.get("args")})
            elif p["kind"] == "text" and p.get("content"):
                rows.append({**base, "type": "said", "text": p["content"]})
        return rows
    if kind == "agent_step" and e.get("node") == "model_request":
        return [{**base, "type": "tool_result", "tool": p["tool"], "text": p.get("content")}
                for p in d.get("parts", []) if p["kind"] == "tool-return" and p["tool"] != "final_result"]
    return []


@app.get("/api/events")
async def events(
    limit: int = Query(50, ge=1, le=500),
    ticket_id: int | None = None,
    after: int | None = Query(None, description="only events with event_id > after (for incremental refresh)"),
):
    """Recent agent events: what each agent said and which tools it used. Newest last."""
    raw = json.loads(AUDIT_PATH.read_text()) if AUDIT_PATH.exists() else []
    rows = []
    for i, e in enumerate(raw):
        if after is not None and i <= after:
            continue
        if ticket_id is not None and e.get("ticket_id") != ticket_id:
            continue
        rows.extend(_flatten(i, e))
    last_reset = max((i for i, e in enumerate(raw) if e["event"] == "database_reset"), default=-1)
    return {"last_event_id": len(raw) - 1, "last_reset_event_id": last_reset, "events": rows[-limit:]}


# ------------------------------------------------------------------ payments (human)

class Decision(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the human clicking the button")


@app.get("/api/payments")
async def payment_requests(status: str = "pending"):
    """Payment / purchase-order requests the agents queued (default: pending ones), with a readable label."""
    data = await mcp_call("list_payment_requests", {"status": status})
    vendors = {v["vendor_id"]: v["name"] for v in (await mcp_call("list_vendors"))["vendors"]}
    tickets = {t["id"]: t for t in (await mcp_call("list_tickets"))["tickets"]}
    for r in data["requests"]:
        r["vendor_name"] = vendors.get(r["vendor_id"])
        t = tickets.get(r["ticket_id"], {})
        r["ticket_subject"], r["requester"] = t.get("subject"), t.get("requester")
        if r["kind"] == "invoice":
            r["label"] = f"Invoice #{r['ref_id']} · {r['vendor_name']}"
        elif r["kind"] == "rent":
            r["label"] = f"Rent · lease {r['ref_id']} · {t.get('requester') or 'landlord'}"
        else:
            r["label"] = f"Purchase order · {r['qty']} × {r['sku']} {r['size']} · {r['vendor_name']}"
    return data


async def _decide(request_id: int, approve: bool, who: str) -> dict:
    result = await state["mcp"].direct_call_tool(
        "approve_payment_request", {"request_id": request_id, "approve": approve, "approved_by": who})
    req = next((r for r in (await mcp_call("list_payment_requests", {"status": "all"}))["requests"]
                if r["id"] == request_id), {})
    AuditLog(new_session_id("api-approve-")).append(
        "human_decision", ticket_id=req.get("ticket_id"), agent="human",
        details={"request_id": request_id, "decision": "approve" if approve else "reject",
                 "approved_by": who, "result": result})
    if "error" in result:
        raise HTTPException(400, result["error"])
    if result.get("refused"):
        raise HTTPException(409, result["reason"])
    return result


@app.post("/api/payments/{request_id}/approve")
async def approve_payment(request_id: int, body: Decision):
    """HUMAN click: approve and pay a queued payment or purchase order. The only route that changes cash."""
    return await _decide(request_id, True, body.approved_by)


@app.post("/api/payments/{request_id}/reject")
async def reject_payment(request_id: int, body: Decision):
    """HUMAN click: reject a queued request (no money moves)."""
    return await _decide(request_id, False, body.approved_by)


# ------------------------------------------------------------------ cash / reset

@app.get("/api/cash")
async def cash():
    """Current checking balance from cash_accounts (plus what is pending approval)."""
    pos = await mcp_call("get_cash_position")
    checking = next((a for a in pos["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account in cash_accounts.")
    return {
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["date"],
        "shop_today": pos["shop_today"],
        "pending_total": pos["pending_total"],
        "balance_after_pending": pos["cash_after_all_pending"],
    }


@app.post("/api/reset")
async def reset():
    """Copy data/campus_customs.db over the working copy for a fresh run (audit trail is kept)."""
    if state["active_run"]:
        raise HTTPException(409, "An agent run is in progress; wait for it to finish.")
    reset_working_db()
    state["runs"].clear()
    AuditLog(new_session_id("api-reset-")).append("database_reset", details={"source": "api"})
    return {"reset": True, **(await cash())}


@app.get("/api/health")
async def health():
    return {"ok": True}
