"""Campus Customs MCP server.

The single tool layer for every HW5 agent. All tools read/write the working
copy data/campus_customs_new.db; the original campus_customs.db is never
touched. Tools return only values stored in the database (plus date math
against desk.date_today and arithmetic on stored values) and return an
`error` key instead of guessing when a record is missing.

Money rules enforced here, not in prompts:
  * Agents can only *request* payments/purchase orders; amounts are always
    read from the database, never supplied by the agent.
  * Only `approve_payment_request` moves cash. It is human-only: the backend
    never gives it to an agent, and it requires a named human approver.
  * A payment that would make the balance negative is refused.
"""

import calendar
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}
TICKET_STATUSES = ("open", "in_progress", "waiting_approval", "waiting_vendor", "resolved")

mcp = FastMCP("campus-customs")

# Tables the agent team adds to the working copy. The original database does
# not have them; they are recreated after every reset.
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice | rent | purchase_order
    ref_id INTEGER,                  -- invoices.id or leases.id (NULL for purchase_order)
    vendor_id INTEGER,
    sku TEXT,
    size TEXT,
    qty INTEGER,
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    ticket_id INTEGER,
    requested_by TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL,            -- pending | paid | rejected
    decided_by TEXT,
    decided_at TEXT,
    payment_id INTEGER,
    eta TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    author_agent TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,            -- always 'draft': nothing is ever sent
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_queue (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    ticket_id INTEGER,
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    instruction TEXT NOT NULL,
    status TEXT NOT NULL,            -- queued | running | done | failed
    result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------- helpers

def _connect(readonly: bool = True) -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    _ensure_schema()  # cheap; restores the working tables after a reset
    uri = f"file:{DB_PATH}?mode={'ro' if readonly else 'rw'}"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema() -> None:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=rw", uri=True)
    with conn:
        conn.executescript(EXTRA_SCHEMA)
    conn.close()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _shop_today(conn: sqlite3.Connection) -> date:
    """The shop's 'today' is desk.date_today, never the system clock."""
    row = conn.execute("SELECT date_today FROM desk").fetchone()
    return date.fromisoformat(row["date_today"])


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _open_invoices(conn: sqlite3.Connection, today: date, vendor_id: int | None = None) -> list[dict]:
    sql = ("SELECT i.id, i.vendor_id, v.name AS vendor, i.amount, i.due_date, i.description "
           "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open'")
    params: tuple = ()
    if vendor_id is not None:
        sql += " AND i.vendor_id = ?"
        params = (vendor_id,)
    rows = conn.execute(sql + " ORDER BY i.due_date", params).fetchall()
    return [
        {
            "invoice_id": r["id"],
            "vendor_id": r["vendor_id"],
            "vendor": r["vendor"],
            "amount": r["amount"],
            "due_date": r["due_date"],
            "days_overdue": max((today - date.fromisoformat(r["due_date"])).days, 0),
            "description": r["description"],
        }
        for r in rows
    ]


def _rows(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- tickets

@mcp.tool
async def list_tickets() -> dict:
    """List every ticket (open or resolved) with its status. Reads tickets and desk."""
    with _connect() as conn:
        today = _shop_today(conn)
        rows = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, status, created_at FROM tickets ORDER BY id"
        ).fetchall()
    return {"shop_today": today.isoformat(), "tickets": _rows(rows)}


@mcp.tool
async def list_open_tickets() -> dict:
    """List every ticket that is not resolved, oldest first. Reads tickets and desk."""
    with _connect() as conn:
        today = _shop_today(conn)
        rows = conn.execute(
            "SELECT id, type, requester, subject, status, created_at FROM tickets "
            "WHERE status != 'resolved' ORDER BY created_at"
        ).fetchall()
    return {"shop_today": today.isoformat(), "tickets": _rows(rows)}


@mcp.tool
async def get_ticket(ticket_id: int) -> dict:
    """Read one ticket with the invoice or lease it links to.

    Reads tickets, plus invoices + vendors (if invoice_id is set), leases (if
    lease_id is set) and desk (shop today).
    """
    with _connect() as conn:
        t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"error": f"Ticket {ticket_id} not found."}
        today = _shop_today(conn)
        result = {"shop_today": today.isoformat(), "ticket": dict(t)}
        if t["invoice_id"] is not None:
            inv = conn.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i "
                "JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", (t["invoice_id"],)
            ).fetchone()
            if inv is not None:
                linked = dict(inv)
                linked["days_overdue"] = max((today - date.fromisoformat(inv["due_date"])).days, 0) \
                    if inv["status"] == "open" else 0
                result["linked_invoice"] = linked
        if t["lease_id"] is not None:
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (t["lease_id"],)).fetchone()
            if lease is not None:
                result["linked_lease"] = dict(lease)
    return result


@mcp.tool
async def update_ticket(
    ticket_id: int,
    status: Literal["open", "in_progress", "waiting_approval", "waiting_vendor", "resolved"],
    note: str,
    agent: str,
) -> dict:
    """Set a ticket's status and append a dated note. Writes tickets."""
    with _connect(readonly=False) as conn:
        t = conn.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"error": f"Ticket {ticket_id} not found."}
        today = _shop_today(conn)
        notes = (t["notes"] or "") + f"\n[{today.isoformat()} {agent}] {note}"
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
    return {"ticket_id": ticket_id, "status": status, "notes": notes}


# ---------------------------------------------------------------- inventory

@mcp.tool
async def check_stock(sku: str, size: str, qty_requested: int) -> dict:
    """Check whether an order can be filled from stock, and the price floor for discounts.

    Reads inventory (on-hand qty for this sku/size, plus other sizes) and
    pricing (unit_cost and list_price). Returns the shortfall and the
    minimum per-unit price (unit_cost) any discount must stay above.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT size, qty, name, location FROM inventory WHERE sku = ?", (sku,)
        ).fetchall()
        if not rows:
            return {"error": f"SKU {sku} not found in inventory."}
        match = next((r for r in rows if r["size"] == size), None)
        if match is None:
            return {"error": f"SKU {sku} has no size {size} in inventory."}

        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()

    on_hand = match["qty"]
    result = {
        "sku": sku,
        "name": match["name"],
        "size": size,
        "location": match["location"],
        "qty_requested": qty_requested,
        "qty_on_hand": on_hand,
        "can_fill_now": min(on_hand, qty_requested),
        "shortfall": max(qty_requested - on_hand, 0),
        "other_sizes_on_hand": {r["size"]: r["qty"] for r in rows if r["size"] != size},
    }
    if price is None:
        result["pricing"] = "No pricing row for this SKU."
    else:
        result["pricing"] = {
            "unit_cost": price["unit_cost"],
            "list_price": price["list_price"],
            "list_total_for_request": round(price["list_price"] * qty_requested, 2),
            "discount_floor_per_unit": price["unit_cost"],
        }
    return result


@mcp.tool
async def list_vendors() -> dict:
    """List every vendor with specialty, lead time, hold status and restock ETA.

    Reads vendors, invoices (open ones put a vendor on hold) and desk. Match a
    product to a vendor by its specialty; the database has no SKU-to-vendor map.
    """
    with _connect() as conn:
        today = _shop_today(conn)
        vendors = conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id").fetchall()
        result = []
        for v in vendors:
            open_inv = _open_invoices(conn, today, v["id"])
            result.append({
                "vendor_id": v["id"],
                "name": v["name"],
                "specialty": v["specialty"],
                "lead_days": v["lead_days"],
                "on_hold": bool(open_inv),
                "blocking_invoice_ids": [i["invoice_id"] for i in open_inv],
                "eta_if_cleared_today": (today + timedelta(days=v["lead_days"])).isoformat(),
            })
    return {"shop_today": today.isoformat(), "vendors": result}


@mcp.tool
async def check_vendor_hold(vendor_id: int) -> dict:
    """Check whether a vendor will ship, and the restock ETA if it can.

    Reads vendors (name, specialty, lead_days), invoices (this vendor's open
    invoices) and desk (shop today). A vendor with any open invoice is on hold
    and will not ship new product until it is paid.
    """
    with _connect() as conn:
        vendor = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,)
        ).fetchone()
        if vendor is None:
            return {"error": f"Vendor {vendor_id} not found."}
        today = _shop_today(conn)
        open_invoices = _open_invoices(conn, today, vendor_id)

    on_hold = bool(open_invoices)
    eta = (today + timedelta(days=vendor["lead_days"])).isoformat()
    return {
        "vendor_id": vendor["id"],
        "name": vendor["name"],
        "specialty": vendor["specialty"],
        "lead_days": vendor["lead_days"],
        "shop_today": today.isoformat(),
        "on_hold": on_hold,
        "open_invoices": [{k: v for k, v in i.items() if k not in ("vendor_id", "vendor")}
                          for i in open_invoices],
        "open_balance": round(sum(i["amount"] for i in open_invoices), 2),
        "eta_if_ordered_today": None if on_hold else eta,
        "eta_if_cleared_today": eta,
    }


# ---------------------------------------------------------------- facilities

@mcp.tool
async def check_rent_due(lease_id: int) -> dict:
    """Check when rent is due on a lease and whether checking can cover it.

    Reads leases (monthly_rent, next_due, landlord), desk (shop today) and
    cash_accounts (current balances). Does not pay anything; payment needs
    human approval through a separate tool.
    """
    with _connect() as conn:
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
            "FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"error": f"Lease {lease_id} not found."}
        today = _shop_today(conn)
        accounts = conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall()

    days_until_due = (date.fromisoformat(lease["next_due"]) - today).days
    return {
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": lease["monthly_rent"],
        "next_due": lease["next_due"],
        "shop_today": today.isoformat(),
        "days_until_due": days_until_due,
        "overdue": days_until_due < 0,
        "cash_accounts": [
            {
                "name": a["name"],
                "balance": a["balance"],
                "as_of": a["date"],
                "covers_rent": a["balance"] >= lease["monthly_rent"],
                "balance_after_rent": round(a["balance"] - lease["monthly_rent"], 2),
            }
            for a in accounts
        ],
    }


# ---------------------------------------------------------------- accounting

@mcp.tool
async def get_cash_position() -> dict:
    """Show cash on hand against everything that wants it.

    Reads cash_accounts, invoices + vendors (open bills, days overdue), leases
    (next rent due), payment_requests (pending, not yet approved) and desk.
    """
    with _connect() as conn:
        today = _shop_today(conn)
        accounts = _rows(conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall())
        open_inv = _open_invoices(conn, today)
        leases = conn.execute("SELECT id, landlord, monthly_rent, next_due FROM leases").fetchall()
        pending = _rows(conn.execute(
            "SELECT id, kind, ref_id, amount, ticket_id, requested_by FROM payment_requests "
            "WHERE status = 'pending' ORDER BY id"
        ).fetchall())

    total_cash = round(sum(a["balance"] for a in accounts), 2)
    pending_total = round(sum(p["amount"] for p in pending), 2)
    return {
        "shop_today": today.isoformat(),
        "cash_accounts": accounts,
        "total_cash": total_cash,
        "open_invoices": open_inv,
        "open_invoice_total": round(sum(i["amount"] for i in open_inv), 2),
        "rent": [
            {
                "lease_id": l["id"],
                "landlord": l["landlord"],
                "monthly_rent": l["monthly_rent"],
                "next_due": l["next_due"],
                "days_until_due": (date.fromisoformat(l["next_due"]) - today).days,
            }
            for l in leases
        ],
        "pending_payment_requests": pending,
        "pending_total": pending_total,
        "cash_after_all_pending": round(total_cash - pending_total, 2),
        "note": "Cash only goes out; no revenue is modeled.",
    }


@mcp.tool
async def check_margin(sku: str, unit_price: float, qty: int) -> dict:
    """Check the margin on selling `qty` of `sku` at a proposed `unit_price`.

    Reads pricing (unit_cost, list_price). Flags any price below unit_cost.
    """
    with _connect() as conn:
        p = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
    if p is None:
        return {"error": f"No pricing row for SKU {sku}."}
    margin_unit = round(unit_price - p["unit_cost"], 2)
    return {
        "sku": sku,
        "qty": qty,
        "unit_cost": p["unit_cost"],
        "list_price": p["list_price"],
        "proposed_unit_price": unit_price,
        "discount_vs_list_pct": round((1 - unit_price / p["list_price"]) * 100, 1),
        "margin_per_unit": margin_unit,
        "margin_pct_of_price": round(margin_unit / unit_price * 100, 1) if unit_price else None,
        "total_price": round(unit_price * qty, 2),
        "total_margin": round(margin_unit * qty, 2),
        "below_cost": unit_price < p["unit_cost"],
    }


@mcp.tool
async def request_payment(
    kind: Literal["invoice", "rent"],
    ref_id: int,
    ticket_id: int,
    requested_by: str,
    reason: str,
) -> dict:
    """Queue a payment for HUMAN approval. Does not move any money.

    kind='invoice' -> ref_id is invoices.id; kind='rent' -> ref_id is leases.id.
    The amount is read from the database, never supplied by the caller.
    Reads invoices/leases and cash_accounts; writes payment_requests.
    """
    with _connect(readonly=False) as conn:
        if kind == "invoice":
            row = conn.execute("SELECT amount, status, vendor_id FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if row is None:
                return {"error": f"Invoice {ref_id} not found."}
            if row["status"] != "open":
                return {"error": f"Invoice {ref_id} is '{row['status']}', not open; nothing to pay."}
            amount, vendor_id = row["amount"], row["vendor_id"]
        else:
            row = conn.execute("SELECT monthly_rent FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if row is None:
                return {"error": f"Lease {ref_id} not found."}
            amount, vendor_id = row["monthly_rent"], None

        dup = conn.execute(
            "SELECT id FROM payment_requests WHERE kind = ? AND ref_id = ? AND status = 'pending'",
            (kind, ref_id),
        ).fetchone()
        if dup is not None:
            return {"request_id": dup["id"], "status": "pending", "note": "Already queued; not duplicated."}

        account = conn.execute("SELECT name, balance FROM cash_accounts ORDER BY balance DESC").fetchone()
        cur = conn.execute(
            "INSERT INTO payment_requests (kind, ref_id, vendor_id, amount, account, ticket_id, "
            "requested_by, reason, status, created_at) VALUES (?,?,?,?,?,?,?,?, 'pending', ?)",
            (kind, ref_id, vendor_id, amount, account["name"], ticket_id, requested_by, reason, _now()),
        )
    return {
        "request_id": cur.lastrowid,
        "status": "pending",
        "kind": kind,
        "ref_id": ref_id,
        "amount": amount,
        "account": account["name"],
        "account_balance_now": account["balance"],
        "covers_now": account["balance"] >= amount,
        "note": "Waiting for human approval. No money has moved.",
    }


@mcp.tool
async def request_purchase_order(
    vendor_id: int,
    sku: str,
    size: str,
    qty: int,
    ticket_id: int,
    requested_by: str,
    reason: str,
) -> dict:
    """Queue a restock purchase order (paid up front) for HUMAN approval.

    Cost = qty x pricing.unit_cost, read from the database. Reads vendors,
    invoices (hold check), inventory, pricing, cash_accounts; writes
    payment_requests. Does not move money or change inventory.
    """
    if qty <= 0:
        return {"error": "qty must be positive."}
    with _connect(readonly=False) as conn:
        today = _shop_today(conn)
        vendor = conn.execute("SELECT name, lead_days FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"error": f"Vendor {vendor_id} not found."}
        if conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone() is None:
            return {"error": f"{sku} size {size} is not a stocked item."}
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return {"error": f"No pricing row for SKU {sku}."}

        dup = conn.execute(
            "SELECT id FROM payment_requests WHERE kind = 'purchase_order' AND vendor_id = ? "
            "AND sku = ? AND size = ? AND status = 'pending'", (vendor_id, sku, size),
        ).fetchone()
        if dup is not None:
            return {"request_id": dup["id"], "status": "pending", "note": "Already queued; not duplicated."}

        amount = round(qty * price["unit_cost"], 2)
        blocking = [i["invoice_id"] for i in _open_invoices(conn, today, vendor_id)]
        account = conn.execute("SELECT name, balance FROM cash_accounts ORDER BY balance DESC").fetchone()
        cur = conn.execute(
            "INSERT INTO payment_requests (kind, vendor_id, sku, size, qty, amount, account, ticket_id, "
            "requested_by, reason, status, created_at) VALUES ('purchase_order',?,?,?,?,?,?,?,?,?, 'pending', ?)",
            (vendor_id, sku, size, qty, amount, account["name"], ticket_id, requested_by, reason, _now()),
        )
    return {
        "request_id": cur.lastrowid,
        "status": "pending",
        "vendor": vendor["name"],
        "sku": sku,
        "size": size,
        "qty": qty,
        "unit_cost": price["unit_cost"],
        "amount": amount,
        "vendor_on_hold": bool(blocking),
        "blocking_invoice_ids": blocking,
        "eta_if_approved_today": None if blocking else (today + timedelta(days=vendor["lead_days"])).isoformat(),
        "account_balance_now": account["balance"],
        "covers_now": account["balance"] >= amount,
        "note": "Waiting for human approval. Cannot be paid while the vendor is on hold.",
    }


@mcp.tool
async def list_payment_requests(status: Literal["pending", "paid", "rejected", "all"] = "pending") -> dict:
    """List payment / purchase-order requests. Reads payment_requests."""
    with _connect() as conn:
        sql = "SELECT * FROM payment_requests"
        rows = conn.execute(sql + ("" if status == "all" else " WHERE status = ?") + " ORDER BY id",
                            () if status == "all" else (status,)).fetchall()
    return {"status_filter": status, "requests": _rows(rows)}


@mcp.tool
async def approve_payment_request(request_id: int, approve: bool, approved_by: str) -> dict:
    """HUMAN ONLY. Approve (and pay) or reject a queued payment request.

    Never exposed to agents. On approval, in one transaction: checks the bill is
    still open, the vendor is not on hold (purchase orders), and the balance
    covers the amount (refuses rather than go negative); then inserts into
    payments, lowers cash_accounts.balance, and marks the invoice paid /
    advances the lease next_due one month / sets the PO ETA.
    """
    approved_by = approved_by.strip()
    if not approved_by or approved_by.lower() in AGENT_NAMES:
        return {"error": "A named human approver is required."}

    with _connect(readonly=False) as conn:
        req = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"error": f"Payment request {request_id} not found."}
        if req["status"] != "pending":
            return {"error": f"Request {request_id} is already '{req['status']}'."}
        today = _shop_today(conn)

        if not approve:
            conn.execute(
                "UPDATE payment_requests SET status='rejected', decided_by=?, decided_at=? WHERE id=?",
                (approved_by, _now(), request_id),
            )
            return {"request_id": request_id, "status": "rejected", "decided_by": approved_by}

        amount, account = req["amount"], req["account"]
        if req["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                return {"refused": True, "reason": f"Invoice {req['ref_id']} is no longer open."}
        if req["kind"] == "purchase_order":
            blocking = _open_invoices(conn, today, req["vendor_id"])
            if blocking:
                return {"refused": True,
                        "reason": "Vendor is on hold; pay invoice(s) "
                                  f"{[i['invoice_id'] for i in blocking]} first."}

        bal = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if bal is None:
            return {"refused": True, "reason": f"Cash account '{account}' not found."}
        # Conditional update makes the no-negative-balance rule atomic.
        cur = conn.execute(
            "UPDATE cash_accounts SET balance = ROUND(balance - ?, 2), date = ? "
            "WHERE name = ? AND balance >= ?",
            (amount, today.isoformat(), account, amount),
        )
        if cur.rowcount != 1:
            return {"refused": True,
                    "reason": f"Insufficient funds: {account} has {bal['balance']}, needs {amount}. "
                              "No negative balances."}

        ref_id = req["ref_id"] if req["kind"] != "purchase_order" else request_id
        pay = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
            (req["kind"], ref_id, amount, account, today.isoformat(), approved_by),
        )
        updates: dict = {}
        eta = None
        if req["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            updates["invoice"] = {"id": req["ref_id"], "status": "paid"}
        elif req["kind"] == "rent":
            lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()
            new_due = _add_month(date.fromisoformat(lease["next_due"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, req["ref_id"]))
            updates["lease"] = {"id": req["ref_id"], "old_next_due": lease["next_due"], "next_due": new_due}
        else:
            lead = conn.execute("SELECT lead_days FROM vendors WHERE id = ?", (req["vendor_id"],)).fetchone()
            eta = (today + timedelta(days=lead["lead_days"])).isoformat()
            updates["purchase_order"] = {"eta": eta}

        conn.execute(
            "UPDATE payment_requests SET status='paid', decided_by=?, decided_at=?, payment_id=?, eta=? WHERE id=?",
            (approved_by, _now(), pay.lastrowid, eta, request_id),
        )
        new_bal = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()

    return {
        "request_id": request_id,
        "status": "paid",
        "payment_id": pay.lastrowid,
        "amount": amount,
        "account": account,
        "balance_before": bal["balance"],
        "balance_after": new_bal["balance"],
        "approved_by": approved_by,
        "updated": updates,
    }


# ---------------------------------------------------------------- drafts

@mcp.tool
async def save_draft(ticket_id: int, author_agent: str, recipient: str, subject: str, body: str) -> dict:
    """Save a message draft on the board. NEVER sends anything. Writes drafts."""
    with _connect(readonly=False) as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"Ticket {ticket_id} not found."}
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, author_agent, recipient, subject, body, status, created_at) "
            "VALUES (?,?,?,?,?, 'draft', ?)",
            (ticket_id, author_agent, recipient, subject, body, _now()),
        )
    return {"draft_id": cur.lastrowid, "status": "draft", "sent": False}


@mcp.tool
async def list_drafts(ticket_id: int | None = None) -> dict:
    """List saved drafts, optionally for one ticket. Reads drafts."""
    with _connect() as conn:
        if ticket_id is None:
            rows = conn.execute("SELECT * FROM drafts ORDER BY id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    return {"drafts": _rows(rows)}


# ---------------------------------------------------------------- agent work queue

@mcp.tool
async def enqueue_task(session_id: str, ticket_id: int, from_agent: str, to_agent: str, instruction: str) -> dict:
    """Put a delegated task on the agent work queue. Writes agent_queue."""
    now = _now()
    with _connect(readonly=False) as conn:
        cur = conn.execute(
            "INSERT INTO agent_queue (session_id, ticket_id, from_agent, to_agent, instruction, status, "
            "created_at, updated_at) VALUES (?,?,?,?,?, 'queued', ?, ?)",
            (session_id, ticket_id, from_agent, to_agent, instruction, now, now),
        )
    return {"task_id": cur.lastrowid, "status": "queued"}


@mcp.tool
async def update_task(
    task_id: int,
    status: Literal["queued", "running", "done", "failed"],
    result: str | None = None,
) -> dict:
    """Move a queued task to running / done / failed and store its result. Writes agent_queue."""
    with _connect(readonly=False) as conn:
        cur = conn.execute(
            "UPDATE agent_queue SET status = ?, result = COALESCE(?, result), updated_at = ? WHERE id = ?",
            (status, result, _now(), task_id),
        )
    if cur.rowcount != 1:
        return {"error": f"Task {task_id} not found."}
    return {"task_id": task_id, "status": status}


@mcp.tool
async def list_queue(
    ticket_id: int | None = None,
    status: Literal["queued", "running", "done", "failed", "all"] = "all",
) -> dict:
    """See who is working on what: the agent work queue. Reads agent_queue."""
    sql = "SELECT id, session_id, ticket_id, from_agent, to_agent, instruction, status, result, " \
          "created_at, updated_at FROM agent_queue WHERE 1=1"
    params: list = []
    if ticket_id is not None:
        sql += " AND ticket_id = ?"
        params.append(ticket_id)
    if status != "all":
        sql += " AND status = ?"
        params.append(status)
    with _connect() as conn:
        rows = conn.execute(sql + " ORDER BY id", params).fetchall()
    return {"tasks": _rows(rows)}


if __name__ == "__main__":
    mcp.run(show_banner=False)
