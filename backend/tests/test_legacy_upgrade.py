"""Exercise the released pre-v2 schema and payloads without initializing current Store first."""

import hashlib
import hmac
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from seopilot.app import create_app
from seopilot.fix_models import Project
from seopilot.models import Audit
from seopilot.storage import Store

SCHEMA = Path(__file__).parent / "fixtures" / "legacy-v2-schema.sql"
ORIGIN = "https://legacy.example.org"
PEER = "198.51.100.27"
SALT = "0123456789abcdef" * 4  # Public synthetic test salt, never a credential.
PROJECT_ID = "66666666-6666-4666-8666-666666666666"
NOW = datetime.fromisoformat("2026-10-24T10:05:00+00:00").timestamp()
TABLES = ("projects", "audits", "pages", "issues", "recommendations", "decisions",
          "local_settings", "admissions", "ai_calls")


def legacy_payload():
    # Frozen pre-v2 public shape: no rule/score versions, discovery, structured data,
    # verification URLs, fixture revision or score breakdown from later releases.
    return {
        "id": "11111111-1111-4111-8111-111111111111", "url": ORIGIN + "/", "origin": ORIGIN,
        "mode": "live", "status": "completed", "created_at": "2026-10-24T10:00:00+00:00",
        "updated_at": "2026-10-24T10:04:00+00:00", "completed_at": "2026-10-24T10:02:00+00:00",
        "business_context": "Original business context", "allow_ai": True,
        "options": {"page_limit": 15, "max_depth": 2, "delay_ms": 750, "timeout_seconds": 10.0,
                    "response_bytes": 2097152, "total_seconds": 120},
        "progress": {"stage": "completed", "visited": 1, "discovered": 1, "limit": 15, "message": "Original result"},
        "pages": [{"id": "22222222-2222-4222-8222-222222222222", "url": ORIGIN + "/",
                   "depth": 0, "status_code": 200, "outcome": "html", "content_type": "text/html",
                   "title": "Legacy page", "description": "", "headings": [], "canonicals": [],
                   "robots": [], "images": [], "links": [], "text_excerpt": "Original retained excerpt",
                   "error": None, "truncated_fields": []}],
        "issues": [{"id": "33333333-3333-4333-8333-333333333333", "rule_id": "missing_description",
                    "title": "Missing description", "url": ORIGIN + "/", "severity": "Medium",
                    "category": "Metadata", "explanation": "No description was observed.", "page_ids": [],
                    "evidence": [{"id": "44444444-4444-4444-8444-444444444444", "field": "description", "value": ""}],
                    "recommended_fix": "Write an accurate description.", "source": "deterministic", "is_site": False,
                    "estimated_impact": "Estimated improvement to clarity or crawlability; ranking outcomes are not guaranteed."}],
        "recommendations": [{"id": "55555555-5555-4555-8555-555555555555", "source": "rule",
                             "kind": "description", "title": "Add a description", "url": ORIGIN + "/",
                             "rationale": "The description is missing.", "priority": "Medium", "page_id": None,
                             "issue_ids": [], "evidence_ids": [], "basis": "observed",
                             "suggested_value": "An accurate description of the original page.",
                             "status": "approved", "decided_at": "2026-10-24T10:04:00+00:00"}],
        "warnings": [], "coverage": {"attempted": 1, "assessed": 1, "blocked": 0,
                                      "failed": 0, "unchecked": 0, "truncated": False},
        "score": {"value": 95, "assessed_pages": 1, "formula": "Original frozen scoring formula"},
        "ai_status": "available", "summary": "Original saved result",
    }


def raw_snapshot(path):
    with sqlite3.connect(path) as db:
        return {table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() for table in TABLES}


@pytest.fixture
def legacy_database(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    payload = legacy_payload()
    identity = hmac.new(SALT.encode(), PEER.encode(), hashlib.sha256).hexdigest()
    fingerprint = hashlib.sha256(json.dumps({"url": payload["url"], "context": payload["business_context"],
        "options": payload["options"], "allow_ai": payload["allow_ai"]}, sort_keys=True).encode()).hexdigest()
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.read_text(encoding="utf-8"))
        db.execute("INSERT INTO projects VALUES(?,?)", (PROJECT_ID, ORIGIN))
        db.execute("INSERT INTO audits VALUES(?,?,?,?,?,?,?,?,?,?,?)", (payload["id"], PROJECT_ID,
            payload["url"], "live", payload["status"], payload["created_at"], payload["updated_at"],
            95, 1, 1, json.dumps(payload)))
        for table in ("pages", "issues", "recommendations"):
            for record in payload[table]:
                db.execute(f"INSERT INTO {table} VALUES(?,?,?)", (record["id"], payload["id"], json.dumps(record)))
        for event, status, stamp in (("77777777-7777-4777-8777-777777777777", "rejected", "2026-10-24T10:03:00+00:00"),
                                     ("88888888-8888-4888-8888-888888888888", "approved", "2026-10-24T10:04:00+00:00")):
            db.execute("INSERT INTO decisions VALUES(?,?,?,?,?)", (event, payload["id"],
                payload["recommendations"][0]["id"], status, stamp))
        db.execute("INSERT INTO local_settings VALUES('quota_salt',?)", (SALT,))
        db.execute("INSERT INTO admissions VALUES(?,?,?,?)", (payload["id"], identity, fingerprint, NOW - 300))
        db.execute("INSERT INTO ai_calls VALUES(?,?,?)", (7, payload["id"], NOW - 250))
        db.execute("INSERT INTO ai_calls VALUES(?,?,?)", (8, payload["id"], NOW - 240))
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='fix_runs'").fetchone()
    monkeypatch.setattr("seopilot.storage.time.time", lambda: NOW)
    return path, payload


def same_request(payload, **changes):
    return Audit(url=payload["url"], origin=payload["origin"], business_context=payload["business_context"],
                 options=payload["options"], allow_ai=changes.pop("allow_ai", True), **changes)


def test_real_legacy_schema_upgrade_preserves_every_existing_row_and_decision(legacy_database):
    path, payload = legacy_database
    before = raw_snapshot(path)
    store = Store(path)
    assert raw_snapshot(path) == before
    audit = store.get(payload["id"])
    assert audit.score.value == 95 and audit.score.breakdown is None and audit.score.version == "1"
    assert audit.rules_version == "1" and audit.discovery is None and audit.demo_revision is None
    assert audit.pages[0].structured_data is None and audit.verification_urls == []
    assert audit.recommendations[0].status == "approved"
    assert audit.recommendations[0].decided_at == "2026-10-24T10:04:00+00:00"
    assert [item["status"] for item in store.decisions(audit.id)] == ["rejected", "approved"]
    assert store.quota(PEER, at=NOW)["used"] == 1 and store.ai_calls_remaining(20) == 18
    assert not store.reserve_ai_call(audit.id, 20)
    project = store.fixes.connect(Project(name="New mapping", production_origin=ORIGIN, repository_id=7,
        installation_id=3, repository_owner="owner", repository_name="site", base_branch="main"))
    assert project.id == PROJECT_ID
    assert raw_snapshot(path) == before
    assert Store(path).decide(payload["recommendations"][0]["id"], "approved").decided_at == audit.recommendations[0].decided_at
    assert raw_snapshot(path) == before
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    assert Store(path).decide(payload["recommendations"][0]["id"], "rejected").status == "rejected"
    assert len(Store(path).decisions(audit.id)) == 3
    assert Store(path).get(audit.id).score == audit.score


@pytest.mark.parametrize("status", ["completed", "partial", "queued", "crawling", "analyzing", "reviewing"])
def test_unchanged_legacy_request_reuses_original_audit_without_new_admission(legacy_database, status):
    path, payload = legacy_database
    with sqlite3.connect(path) as db:
        payload["status"] = status
        db.execute("UPDATE audits SET status=?,payload=?", (status, json.dumps(payload)))
    before = raw_snapshot(path)
    store = Store(path)
    reused, reason, quota = store.admit_audit(same_request(payload), PEER, at=NOW)
    assert reason == "reused" and reused.id == payload["id"]
    assert quota["used"] == 1 and store.ai_calls_remaining(20) == 18
    assert raw_snapshot(path) == before


def test_legacy_reuse_remains_available_after_daily_allowance_is_exhausted(legacy_database):
    path, payload = legacy_database
    store = Store(path)
    for suffix in ("second", "third"):
        candidate = same_request(payload)
        candidate.url = ORIGIN + "/" + suffix
        assert store.admit_audit(candidate, PEER, at=NOW)[1] == "created"
    before = raw_snapshot(path)
    reused, reason, quota = store.admit_audit(same_request(payload), PEER, at=NOW)
    assert reason == "reused" and reused.id == payload["id"] and quota["remaining"] == 0
    assert store.ai_calls_remaining(20) == 18 and raw_snapshot(path) == before


def test_api_reuses_recent_legacy_result_and_preserves_decisions_and_charges(legacy_database):
    path, payload = legacy_database
    before = raw_snapshot(path)
    with TestClient(create_app(path, start_worker=False), base_url="http://localhost", client=(PEER, 12345)) as client:
        response = client.post("/api/audits", json={"url": payload["url"], "business_context": payload["business_context"],
            "options": payload["options"], "allow_ai": True})
        assert response.status_code == 202 and response.headers["X-Audit-Reused"] == "true"
        assert response.json()["id"] == payload["id"]
        assert response.json()["recommendations"][0]["status"] == "approved"
        usage = client.get("/api/usage").json()
        assert usage["used"] == 1 and usage["ai_calls_remaining"] == 18
    assert raw_snapshot(path) == before


@pytest.mark.parametrize("change", ["peer", "context", "options", "ai", "verification", "expired"])
def test_legacy_reuse_does_not_relax_request_identity_or_scope(legacy_database, change):
    path, payload = legacy_database
    store = Store(path)
    candidate = same_request(payload)
    peer, tick = PEER, NOW
    if change == "peer":
        peer = "198.51.100.28"
    elif change == "context":
        candidate.business_context = "A different business"
    elif change == "options":
        candidate.options.page_limit = 1
    elif change == "ai":
        candidate.allow_ai = False
    elif change == "verification":
        candidate.verification_urls = [candidate.url]
    elif change == "expired":
        tick += 600  # Admission is now exactly 900 seconds old.
    created, reason, _ = store.admit_audit(candidate, peer, at=tick)
    assert reason == "created" and created.id != payload["id"]
    assert store.ai_calls_remaining(20) == 18
