"""V2 state and private artifact retention, using the existing SQLite transaction boundary."""

import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path

from .fix_models import FindingDisposition, FixRun, Project
from .models import now

TERMINAL = {"cancelled", "expired", "conflict", "failed", "live_verified"}


class FixStore:
    def __init__(self, store):
        self.store = store
        self.artifacts = store.path.parent / "fix-artifacts"
        with store.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS project_connections(
                    id TEXT PRIMARY KEY REFERENCES projects(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS fix_runs(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    audit_id TEXT NOT NULL REFERENCES audits(id), status TEXT NOT NULL,
                    created_at TEXT NOT NULL, expires_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS fixes_project ON fix_runs(project_id,created_at);
                CREATE TABLE IF NOT EXISTS fix_events(
                    id INTEGER PRIMARY KEY, fix_run_id TEXT NOT NULL REFERENCES fix_runs(id),
                    status TEXT NOT NULL, recorded_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS publications(
                    fix_run_id TEXT PRIMARY KEY REFERENCES fix_runs(id), reserved_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS finding_dispositions(
                    id INTEGER PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES audits(id),
                    issue_id TEXT NOT NULL, payload TEXT NOT NULL);
                PRAGMA user_version=3;
            """)

    def projects(self) -> list[Project]:
        with self.store.connection() as db:
            return [Project.model_validate_json(row[0]) for row in db.execute(
                "SELECT payload FROM project_connections ORDER BY id")]

    def project(self, project_id: str) -> Project | None:
        return next((item for item in self.projects() if item.id == project_id), None)

    def save_project(self, project: Project):
        with self.store.connection() as db:
            db.execute("INSERT INTO project_connections VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                       (project.id, project.model_dump_json()))

    def connect(self, project: Project) -> Project:
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO projects VALUES(?,?)", (project.id, project.production_origin))
            project.id = db.execute("SELECT id FROM projects WHERE origin=?", (project.production_origin,)).fetchone()[0]
            previous = db.execute("SELECT payload FROM project_connections WHERE id=?", (project.id,)).fetchone()
            if previous and Project.model_validate_json(previous[0]).connected:
                raise ValueError("Disconnect the existing mapping before replacing it.")
            db.execute("INSERT INTO project_connections VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                       (project.id, project.model_dump_json()))
        return project

    @staticmethod
    def _save(db, run: FixRun):
        previous = db.execute("SELECT payload FROM fix_runs WHERE id=?", (run.id,)).fetchone()
        if previous:
            old = FixRun.model_validate_json(previous[0])
            if old.status != "preparing":
                fields = ("id", "project_id", "audit_id", "repository_id", "base_branch", "base_sha", "patch_hash", "targets", "changed_files", "changed_lines", "branch", "created_at")
                if any(getattr(old, field) != getattr(run, field) for field in fields):
                    raise ValueError("A reviewed proposal is immutable. Generate a new proposal for different changes.")
        run.updated_at = now()
        db.execute("""INSERT INTO fix_runs VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            status=excluded.status,payload=excluded.payload""", (run.id, run.project_id, run.audit_id, run.status,
            run.created_at, run.expires_at, run.model_dump_json()))
        db.execute("INSERT INTO fix_events(fix_run_id,status,recorded_at) VALUES(?,?,?)", (run.id, run.status, run.updated_at))

    def save(self, run: FixRun):
        with self.store.connection() as db:
            self._save(db, run)

    def create(self, run: FixRun):
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute("SELECT status FROM fix_runs WHERE project_id=?", (run.project_id,)).fetchall()
            if any(row[0] not in TERMINAL for row in active):
                raise ValueError("This project already has an active fix run. Cancel it before creating another.")
            self._save(db, run)

    def get(self, run_id: str) -> FixRun | None:
        with self.store.connection() as db:
            row = db.execute("SELECT payload FROM fix_runs WHERE id=?", (run_id,)).fetchone()
            return FixRun.model_validate_json(row[0]) if row else None

    def history(self) -> list[FixRun]:
        with self.store.connection() as db:
            return [FixRun.model_validate_json(row[0]) for row in db.execute(
                "SELECT payload FROM fix_runs ORDER BY created_at DESC LIMIT 100")]

    def all_runs(self, project_id: str | None = None) -> list[FixRun]:
        with self.store.connection() as db:
            rows = db.execute("SELECT payload FROM fix_runs" + (" WHERE project_id=?" if project_id else ""),
                              (project_id,) if project_id else ()).fetchall()
            return [FixRun.model_validate_json(row[0]) for row in rows]

    def reserve_publication(self, run_id: str, *, at: float | None = None) -> bool:
        tick = time.time() if at is None else at
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM publications WHERE fix_run_id=?", (run_id,)).fetchone():
                return True
            if db.execute("SELECT COUNT(*) FROM publications WHERE reserved_at>?", (tick - 86400,)).fetchone()[0] >= 2:
                return False
            db.execute("INSERT INTO publications VALUES(?,?)", (run_id, tick))
            return True

    def publication_remaining(self) -> int:
        with self.store.connection() as db:
            used = db.execute("SELECT COUNT(*) FROM publications WHERE reserved_at>?", (time.time()-86400,)).fetchone()[0]
            return max(0, 2-used)

    def write_artifact(self, run_id: str, payload: dict):
        # Caller uses generated UUIDs; resolve again before any filesystem mutation.
        target = self._artifact_path(run_id)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = target.with_suffix("."+secrets.token_hex(8)+".tmp")
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=True))
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def _artifact_path(self, run_id: str) -> Path:
        from uuid import UUID

        name = str(UUID(run_id)) + ".json"
        root = self.artifacts.resolve()
        path = (root / name).resolve()
        if path.parent != root:
            raise ValueError("Invalid artifact path")
        return path

    def artifact(self, run: FixRun) -> dict:
        if run.source_purged or datetime.fromisoformat(run.expires_at).timestamp() <= time.time():
            raise ValueError("The private patch expired or was deleted. Generate a new proposal.")
        try:
            path = self._artifact_path(run.id)
            if path.stat().st_size > 4 * 1024 * 1024:
                raise ValueError("Invalid private artifact")
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            raise ValueError("Private patch is unavailable. Generate a new proposal.") from None

    def purge(self, run: FixRun):
        self._artifact_path(run.id).unlink(missing_ok=True)
        run.source_purged = True
        self.save(run)

    def cleanup(self):
        for run in self.all_runs():
            if not run.source_purged and datetime.fromisoformat(run.expires_at).timestamp() <= time.time():
                if run.status in {"preparing", "proposed"}:
                    run.status = "expired"
                    run.message = "Private patch retention expired. Generate a new proposal."
                self.purge(run)

    def disposition(self, value: FindingDisposition):
        with self.store.connection() as db:
            db.execute("INSERT INTO finding_dispositions(audit_id,issue_id,payload) VALUES(?,?,?)",
                       (value.audit_id, value.issue_id, value.model_dump_json()))

    def dispositions(self, audit_id: str) -> list[FindingDisposition]:
        with self.store.connection() as db:
            return [FindingDisposition.model_validate_json(row[0]) for row in db.execute(
                "SELECT payload FROM finding_dispositions WHERE audit_id=? ORDER BY id", (audit_id,))]
