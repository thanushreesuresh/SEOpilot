-- Historical pre-repository-workflow schema, copied from storage.py at
-- 3a90c3cd24662eb11bd6ea1067ea7a07a6c754f9 (PRAGMA user_version=2).
-- Intentionally independent of the current Store initializer. Synthetic data only.
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
PRAGMA user_version=2;
