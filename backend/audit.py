"""Append-only audit trail at output/audit_trail.json (a JSON array).

Every agent-loop step is appended as one event. The file is never wiped:
each write reads the existing array, appends, and atomically replaces it.
"""

import json
import os
from datetime import datetime

from backend.config import AUDIT_PATH, AUDIT_TEXT_LIMIT
from backend.models import AuditEvent


def truncate(value, limit: int = AUDIT_TEXT_LIMIT):
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + f"... [truncated {len(text) - limit} chars]"


class AuditLog:
    def __init__(self, session_id: str):
        self.session_id = session_id
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: str, **fields) -> None:
        record = AuditEvent(
            ts=datetime.now().astimezone().isoformat(timespec="milliseconds"),
            session_id=self.session_id,
            event=event,
            **fields,
        ).model_dump(exclude_none=True)

        existing = json.loads(AUDIT_PATH.read_text()) if AUDIT_PATH.exists() else []
        if not isinstance(existing, list):
            raise ValueError(f"{AUDIT_PATH} is not a JSON array; refusing to overwrite it.")
        existing.append(record)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, indent=2, default=str) + "\n")
        os.replace(tmp, AUDIT_PATH)
