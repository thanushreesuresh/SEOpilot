"""Local SQLite repositories. Transactions never span a network request."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import Audit, AuditSummary, Recommendation, new_id, now


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError("Unsupported database version")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, origin TEXT NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS audits(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    url TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    score INTEGER, page_count INTEGER NOT NULL, issue_count INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pages(id TEXT PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES audits(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS issues(id TEXT PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES audits(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS recommendations(id TEXT PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES audits(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES audits(id), recommendation_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('approved','rejected')), decided_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS audits_status ON audits(status, created_at);
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _write(self, db: sqlite3.Connection, audit: Audit):
        audit.updated_at = now()
        db.execute("INSERT OR IGNORE INTO projects(id,origin) VALUES (?,?)", (new_id(), audit.origin or audit.url))
        project_id = db.execute("SELECT id FROM projects WHERE origin=?", (audit.origin or audit.url,)).fetchone()[0]
        db.execute("""INSERT INTO audits VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at,
            score=excluded.score,page_count=excluded.page_count,issue_count=excluded.issue_count,payload=excluded.payload""",
            (audit.id, project_id, audit.url, audit.mode, audit.status, audit.created_at,
             audit.updated_at, audit.score.value, len(audit.pages), len(audit.issues), audit.model_dump_json()))
        for table, records in (("pages", audit.pages), ("issues", audit.issues), ("recommendations", audit.recommendations)):
            # Table identifiers are constants above, never user input.
            db.execute(f"DELETE FROM {table} WHERE audit_id=?", (audit.id,))
            db.executemany(f"INSERT INTO {table}(id,audit_id,payload) VALUES(?,?,?)",
                           [(record.id, audit.id, record.model_dump_json()) for record in records])

    def save(self, audit: Audit):
        with self.connection() as db:
            self._write(db, audit)

    def get(self, audit_id: str) -> Audit | None:
        with self.connection() as db:
            row = db.execute("SELECT payload FROM audits WHERE id=?", (audit_id,)).fetchone()
            return Audit.model_validate_json(row[0]) if row else None

    def history(self) -> list[AuditSummary]:
        with self.connection() as db:
            rows = db.execute("SELECT id,url,mode,status,created_at,score,page_count AS pages,issue_count AS issues FROM audits ORDER BY created_at DESC LIMIT 100").fetchall()
            return [AuditSummary.model_validate(dict(row)) for row in rows]

    def enqueue(self, audit: Audit, max_pending: int = 5) -> bool:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM audits WHERE status IN ('queued','crawling','analyzing','reviewing')").fetchone()[0]
            if count >= max_pending:
                return False
            self._write(db, audit)
            return True

    def claim(self) -> Audit | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM audits WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            audit = Audit.model_validate_json(row[0])
            audit.status = "crawling"
            audit.progress.stage = "crawling"
            self._write(db, audit)
            return audit

    def recover(self):
        with self.connection() as db:
            rows = db.execute("SELECT payload FROM audits WHERE status IN ('crawling','analyzing','reviewing')").fetchall()
            for row in rows:
                audit = Audit.model_validate_json(row[0])
                audit.status = "interrupted"
                audit.progress.stage = "interrupted"
                audit.progress.message = "The server restarted. Start a new audit to retry."
                audit.warnings.append("Audit interrupted by server restart; partial evidence was preserved.")
                self._write(db, audit)

    def decide(self, recommendation_id: str, status: str) -> Recommendation | None:
        if status not in ("approved", "rejected"):
            raise ValueError("Invalid decision")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT audit_id FROM recommendations WHERE id=?", (recommendation_id,)).fetchone()
            if not row:
                return None
            audit = Audit.model_validate_json(db.execute("SELECT payload FROM audits WHERE id=?", (row[0],)).fetchone()[0])
            if audit.status not in ("completed", "partial", "interrupted"):
                raise ValueError("Wait until the audit finishes before reviewing recommendations")
            recommendation = next(item for item in audit.recommendations if item.id == recommendation_id)
            if recommendation.status == status:
                return recommendation
            recommendation.status = status
            recommendation.decided_at = now()
            self._write(db, audit)
            db.execute("INSERT INTO decisions VALUES(?,?,?,?,?)", (new_id(), audit.id, recommendation.id, status, recommendation.decided_at))
            return recommendation

    def decisions(self, audit_id: str) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM decisions WHERE audit_id=? ORDER BY decided_at", (audit_id,))]
