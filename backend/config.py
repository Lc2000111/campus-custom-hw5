"""Paths, model, tool permissions and budget limits for the agent team."""

from pathlib import Path

from pydantic_ai import UsageLimits

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"
MCP_CONFIG = ROOT / ".mcp.json"
MCP_SERVER_NAME = "campus-customs"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
AUDIT_PATH = ROOT / "output" / "audit_trail.json"

MODEL_NAME = "gpt-5.6-luna"          # every agent, through Portkey
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# --- Which MCP tools each agent may call (least privilege). ---------------
AGENT_TOOLS: dict[str, set[str]] = {
    "boss": {
        "list_tickets", "list_open_tickets", "get_ticket", "update_ticket", "get_cash_position",
        "list_payment_requests", "list_drafts", "list_queue",
    },
    "inventory": {
        "get_ticket", "check_stock", "list_vendors", "check_vendor_hold",
    },
    "accounting": {
        "get_ticket", "get_cash_position", "check_margin", "check_vendor_hold",
        "request_payment", "request_purchase_order", "list_payment_requests",
    },
    "facilities": {
        "get_ticket", "check_rent_due", "save_draft", "list_drafts",
    },
    "customer_service": {
        "get_ticket", "save_draft", "list_drafts",
    },
}

# Never handed to any agent: cash movement is human-only, and the work queue is
# written by the orchestrator so agents cannot fake their own task history.
HUMAN_OR_ORCHESTRATOR_ONLY = {"approve_payment_request", "enqueue_task", "update_task"}
for _agent, _tools in AGENT_TOOLS.items():
    assert not _tools & HUMAN_OR_ORCHESTRATOR_ONLY, f"{_agent} must not get {_tools & HUMAN_OR_ORCHESTRATOR_ONLY}"

# --- Token / loop budget, per ticket (shared by every agent in the chain). --
MAX_DELEGATION_DEPTH = 3            # boss -> specialist -> specialist
MAX_DELEGATIONS_PER_TICKET = 8
TICKET_USAGE_LIMITS = UsageLimits(
    request_limit=40,               # model calls across the whole ticket
    tool_calls_limit=60,
    total_tokens_limit=200_000,
)
AGENT_RETRIES = 1                   # retries on bad tool args / output
MODEL_TIMEOUT_S = 90                # per model call (see backend/llm.py)
AUDIT_TEXT_LIMIT = 4000             # chars kept per tool result / message in the audit
