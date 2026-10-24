"""Local SQLite repositories. Transactions never span a network request."""

import hashlib
import hmac
import json
import math
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import Audit, AuditSummary, Recommendation, new_id, now


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3):
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
                CREATE INDEX IF NOT EXISTS audits_mode_created ON audits(mode, created_at);
                CREATE TABLE IF NOT EXISTS local_settings(name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS admissions(
                    audit_id TEXT PRIMARY KEY REFERENCES audits(id), identity TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, admitted_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS admissions_identity ON admissions(identity, admitted_at);
                CREATE TABLE IF NOT EXISTS ai_calls(
                    id INTEGER PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES audits(id), reserved_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ai_calls_time ON ai_calls(reserved_at);
                CREATE INDEX IF NOT EXISTS ai_calls_audit ON ai_calls(audit_id);
            """)
            db.execute("INSERT OR IGNORE INTO local_settings VALUES('quota_salt',?)", (secrets.token_hex(32),))
            self._quota_salt = db.execute("SELECT value FROM local_settings WHERE name='quota_salt'").fetchone()[0].encode()
            if version < 2:
                db.execute("PRAGMA user_version=2")
        from .fix_storage import FixStore

        self.fixes = FixStore(self)

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
        previous = db.execute("SELECT status FROM audits WHERE id=?", (audit.id,)).fetchone()
        if previous and previous[0] == "cancelled" and audit.status != "cancelled":
            # An in-flight callback must not resurrect a cancelled snapshot.
            return
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
            db.execute("BEGIN IMMEDIATE")
            self._write(db, audit)

    def get_or_create_demo(self, candidate: Audit) -> Audit:
        if (candidate.mode != "demo" or not candidate.demo_revision or candidate.status != "completed"
                or candidate.allow_ai or candidate.ai_status != "demo"):
            raise ValueError("Only a completed, explicit offline sample can be reused by revision.")
        with self.connection() as db:
            # Serialize lookup + insertion across requests and server instances.
            # The bundled candidate is prepared before this short transaction.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT payload FROM audits WHERE mode='demo' AND status='completed'
                AND json_extract(payload, '$.demo_revision')=? ORDER BY created_at DESC,id DESC LIMIT 1""",
                             (candidate.demo_revision,)).fetchone()
            if row:
                return Audit.model_validate_json(row[0])
            self._write(db, candidate)
            return candidate

    def is_cancelled(self, audit_id: str) -> bool:
        with self.connection() as db:
            row = db.execute("SELECT status FROM audits WHERE id=?", (audit_id,)).fetchone()
            return bool(row and row[0] == "cancelled")

    def cancel_audit(self, audit_id: str) -> Audit | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM audits WHERE id=?", (audit_id,)).fetchone()
            if row is None:
                return None
            audit = Audit.model_validate_json(row[0])
            if audit.status == "cancelled":
                return audit
            if audit.status not in {"queued", "crawling", "analyzing", "reviewing"}:
                raise ValueError("This audit has already finished and cannot be cancelled.")
            if audit.status == "reviewing" or audit.ai_status == "pending":
                audit.ai_status = "cancelled"
            audit.status = "cancelled"
            audit.completed_at = now()
            audit.progress.stage = "cancelled"
            audit.progress.message = "Audit cancelled. Retained evidence may be incomplete."
            audit.warnings.append(
                "Cancelled by you. The accepted admission and any AI reservations remain charged. "
                "An AI request already in progress may still be billed."
            )
            self._write(db, audit)
            return audit

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

    def _identity_key(self, identity: str) -> str:
        return hmac.new(self._quota_salt, identity.encode(), hashlib.sha256).hexdigest()

    def _quota(self, db, identity: str, tick: float) -> dict:
        row = db.execute("SELECT COUNT(*),MIN(admitted_at) FROM admissions WHERE identity=? AND admitted_at>?",
                         (identity, tick - 86400)).fetchone()
        used, earliest = row
        reset = earliest + 86400 if earliest is not None else None
        return {"limit": 3, "used": used, "remaining": max(0, 3 - used),
                "reset_at": datetime.fromtimestamp(reset, timezone.utc).isoformat() if reset is not None else None,
                "retry_after": max(1, math.ceil(reset - tick)) if used >= 3 else 0}

    def quota(self, identity: str, *, at: float | None = None) -> dict:
        with self.connection() as db:
            return self._quota(db, self._identity_key(identity), time.time() if at is None else at)

    def admit_audit(self, audit: Audit, identity: str, *, at: float | None = None, max_pending: int = 5) -> tuple[Audit | None, str, dict]:
        """Quota, duplicate detection and queue insertion share one write lock."""
        tick = time.time() if at is None else at
        key = self._identity_key(identity)
        fingerprint = hashlib.sha256(json.dumps({"url": audit.url, "context": audit.business_context,
            "options": audit.options.model_dump(), "allow_ai": audit.allow_ai,
            "verification_urls": audit.verification_urls}, sort_keys=True).encode()).hexdigest()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            quota = self._quota(db, key, tick)
            duplicate = db.execute("""SELECT a.payload FROM admissions q JOIN audits a ON a.id=q.audit_id
                WHERE q.identity=? AND q.fingerprint=? AND
                (a.status IN ('queued','crawling','analyzing','reviewing') OR
                 (?=0 AND q.admitted_at>? AND a.status IN ('completed','partial')))
                ORDER BY q.admitted_at DESC LIMIT 1""", (key, fingerprint, bool(audit.verification_urls), tick - 900)).fetchone()
            if duplicate:
                return Audit.model_validate_json(duplicate[0]), "reused", quota
            if not quota["remaining"]:
                return None, "daily", quota
            count = db.execute("SELECT COUNT(*) FROM audits WHERE status IN ('queued','crawling','analyzing','reviewing')").fetchone()[0]
            if count >= max_pending:
                return None, "queue", quota
            self._write(db, audit)
            db.execute("INSERT INTO admissions VALUES(?,?,?,?)", (audit.id, key, fingerprint, tick))
            return audit, "created", self._quota(db, key, tick)

    def reserve_ai_call(self, audit_id: str, daily_limit: int, max_per_audit: int = 2) -> bool:
        """Reservations count even on timeout; never silently retry paid calls."""
        tick = time.time()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            audit = db.execute("SELECT status FROM audits WHERE id=?", (audit_id,)).fetchone()
            if audit is None or audit[0] == "cancelled":
                return False
            global_count = db.execute("SELECT COUNT(*) FROM ai_calls WHERE reserved_at>?", (tick - 86400,)).fetchone()[0]
            audit_count = db.execute("SELECT COUNT(*) FROM ai_calls WHERE audit_id=?", (audit_id,)).fetchone()[0]
            if global_count >= daily_limit or audit_count >= max_per_audit:
                return False
            db.execute("INSERT INTO ai_calls(audit_id,reserved_at) VALUES(?,?)", (audit_id, tick))
            return True

    def ai_calls_remaining(self, daily_limit: int) -> int:
        with self.connection() as db:
            count = db.execute("SELECT COUNT(*) FROM ai_calls WHERE reserved_at>?", (time.time() - 86400,)).fetchone()[0]
            return max(0, daily_limit - count)

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
            if audit.status not in ("completed", "partial", "interrupted", "cancelled"):
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
