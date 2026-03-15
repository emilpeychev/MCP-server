"""SQLite-backed issue memory — stores and queries past troubleshooting sessions.

DB lives in /app/data/issues.db (persisted via the langchain_data volume).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("ISSUE_DB_PATH", "/app/data/issues.db"))

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS issues (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint   TEXT NOT NULL,
    pattern       TEXT NOT NULL,
    resource      TEXT NOT NULL DEFAULT '',
    root_cause    TEXT NOT NULL DEFAULT '',
    findings      TEXT NOT NULL DEFAULT '[]',
    tools_used    TEXT NOT NULL DEFAULT '[]',
    tool_order    TEXT NOT NULL DEFAULT '[]',
    resolved      INTEGER NOT NULL DEFAULT 0,
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_issues_pattern ON issues(pattern);
CREATE INDEX IF NOT EXISTS idx_issues_fingerprint ON issues(fingerprint);
"""


def _fingerprint(pattern: str, resource: str) -> str:
    raw = f"{pattern}:{resource}".lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class IssueRecord:
    pattern: str
    resource: str = ""
    root_cause: str = ""
    findings: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    tool_order: list[str] = field(default_factory=list)
    resolved: bool = False
    fingerprint: str = ""
    id: int | None = None
    created_at: float = 0.0
    updated_at: float = 0.0


class IssueMemory:
    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._ensure_db()

    def _ensure_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_CREATE_TABLE)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path), timeout=5)

    # --- Write ---

    def record_issue(self, issue: IssueRecord) -> int:
        now = time.time()
        fp = issue.fingerprint or _fingerprint(issue.pattern, issue.resource)
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO issues (fingerprint, pattern, resource, root_cause,
                   findings, tools_used, tool_order, resolved, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fp,
                    issue.pattern,
                    issue.resource,
                    issue.root_cause,
                    json.dumps(issue.findings),
                    json.dumps(issue.tools_used),
                    json.dumps(issue.tool_order),
                    int(issue.resolved),
                    now,
                    now,
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def resolve_issue(self, issue_id: int, root_cause: str = "") -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE issues SET resolved = 1, root_cause = ?, updated_at = ? WHERE id = ?",
                (root_cause, time.time(), issue_id),
            )

    # --- Read ---

    def get_similar(self, pattern: str, limit: int = 5) -> list[IssueRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM issues WHERE pattern = ? ORDER BY updated_at DESC LIMIT ?",
                (pattern, limit),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_top_patterns(self, limit: int = 5) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT pattern, COUNT(*) as cnt,
                   SUM(CASE WHEN resolved = 1 THEN 1 ELSE 0 END) as resolved_cnt
                   FROM issues GROUP BY pattern ORDER BY cnt DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [{"pattern": r[0], "count": r[1], "resolved": r[2]} for r in rows]

    def get_common_causes(self, pattern: str, limit: int = 3) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT root_cause, COUNT(*) as cnt FROM issues
                   WHERE pattern = ? AND root_cause != '' AND resolved = 1
                   GROUP BY root_cause ORDER BY cnt DESC LIMIT ?""",
                (pattern, limit),
            ).fetchall()
        return [{"root_cause": r[0], "count": r[1]} for r in rows]

    def get_best_tool_order(self, pattern: str) -> list[str]:
        """Return the most commonly used successful tool order for a pattern."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT tool_order FROM issues
                   WHERE pattern = ? AND resolved = 1 AND tool_order != '[]'
                   ORDER BY updated_at DESC LIMIT 10""",
                (pattern,),
            ).fetchall()
        if not rows:
            return []
        # Pick the most frequent tool_order
        orders: dict[str, int] = {}
        for (raw,) in rows:
            orders[raw] = orders.get(raw, 0) + 1
        best = max(orders, key=orders.get)  # type: ignore[arg-type]
        return json.loads(best)

    def stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
            resolved = conn.execute("SELECT COUNT(*) FROM issues WHERE resolved = 1").fetchone()[0]
        return {"total_issues": total, "resolved": resolved, "unresolved": total - resolved}

    @staticmethod
    def _row_to_record(row: tuple) -> IssueRecord:
        return IssueRecord(
            id=row[0],
            fingerprint=row[1],
            pattern=row[2],
            resource=row[3],
            root_cause=row[4],
            findings=json.loads(row[5]),
            tools_used=json.loads(row[6]),
            tool_order=json.loads(row[7]),
            resolved=bool(row[8]),
            created_at=row[9],
            updated_at=row[10],
        )


# Singleton
_memory: IssueMemory | None = None


def get_memory() -> IssueMemory:
    global _memory
    if _memory is None:
        _memory = IssueMemory()
    return _memory


def record_issue_dict(data: dict) -> dict:
    """MCP-friendly wrapper to record an issue."""
    mem = get_memory()
    rec = IssueRecord(
        pattern=data.get("pattern", ""),
        resource=data.get("resource", ""),
        root_cause=data.get("root_cause", ""),
        findings=data.get("findings", []),
        tools_used=data.get("tools_used", []),
        tool_order=data.get("tool_order", []),
        resolved=data.get("resolved", False),
    )
    issue_id = mem.record_issue(rec)
    return {
        "result": f"Issue recorded with id={issue_id}.",
        "files": [],
        "data": {"issue_id": issue_id, "pattern": rec.pattern, "fingerprint": rec.fingerprint or _fingerprint(rec.pattern, rec.resource)},
    }


def query_history_dict(pattern: str) -> dict:
    """MCP-friendly wrapper to query issue history for a pattern."""
    mem = get_memory()
    similar = mem.get_similar(pattern, limit=5)
    common_causes = mem.get_common_causes(pattern, limit=3)
    best_order = mem.get_best_tool_order(pattern)
    stats = mem.stats()

    return {
        "result": f"Found {len(similar)} past issues for pattern '{pattern}'.",
        "files": [],
        "data": {
            "pattern": pattern,
            "past_issues": [
                {"id": r.id, "root_cause": r.root_cause, "resolved": r.resolved, "resource": r.resource}
                for r in similar
            ],
            "common_causes": common_causes,
            "best_tool_order": best_order,
            "global_stats": stats,
        },
    }
