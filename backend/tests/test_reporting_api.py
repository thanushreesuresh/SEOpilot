import json

from fastapi.testclient import TestClient

from seopilot.app import create_app
from seopilot.models import Audit, Coverage, Evidence, Issue, Page, Score


def stored_audit(store, *, when, title="A useful page title", missing=False):
    page = Page(url="https://example.com/", status_code=200, title=title, description="Useful page evidence")
    audit = Audit(url=page.url, origin="https://example.com", status="completed", allow_ai=False,
                  created_at=when, completed_at=when, pages=[page], coverage=Coverage(attempted=1, assessed=1),
                  score=Score(value=90 if missing else 100, assessed_pages=1))
    if missing:
        audit.issues = [Issue(rule_id="title_missing", title="Missing title", url=page.url, page_ids=[page.id],
            severity="High", category="Metadata", explanation="No title", recommended_fix="Write a title",
            evidence=[Evidence(field="title", value="(missing)")])]
    store.save(audit)
    return audit


def test_reports_and_comparison_preserve_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "private-env-canary-never-export")
    app = create_app(tmp_path/"reports.db", start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        store = app.state.store
        before = stored_audit(store, when="2026-01-01T00:00:00+00:00", title="", missing=True)
        after = stored_audit(store, when="2026-01-02T00:00:00+00:00")
        assert store.reserve_ai_call(before.id, 20)
        quota = store.quota("unknown")
        for format in ("markdown", "csv", "json"):
            response = client.get(f"/api/audits/{before.id}/report/{format}")
            assert response.status_code == 200
            assert response.json()["filename"].endswith({"markdown": ".md", "csv": ".csv", "json": ".json"}[format])
            assert "private-env-canary" not in response.text
            assert response.headers["cache-control"] == "no-store"
        response = client.post("/api/audit-comparisons", json={"before_audit_id": before.id, "after_audit_id": after.id})
        assert response.status_code == 200, response.text
        assert response.json()["counts"]["resolved"] == 1
        assert response.json()["score_delta"] == 10
        assert store.quota("unknown") == quota and store.ai_calls_remaining(20) == 19
        assert len(store.history()) == 2


def test_report_routes_reject_active_and_forged_requests(tmp_path):
    app = create_app(tmp_path/"reports.db", start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        audit = stored_audit(app.state.store, when="2026-01-01T00:00:00+00:00")
        audit.status = "queued"
        app.state.store.save(audit)
        assert client.get(f"/api/audits/{audit.id}/report/markdown").status_code == 409
        assert client.get(f"/api/audits/{audit.id}/report/html").status_code == 422
        assert client.get("/api/audits/forged/report/json").status_code == 422
        assert client.post("/api/audit-comparisons", json={"before_audit_id": "forged", "after_audit_id": audit.id}).status_code == 422
        assert client.post("/api/audit-comparisons", json={"before_audit_id": audit.id, "after_audit_id": audit.id}).status_code == 409


def test_comparison_rejects_wrong_direction_origin_and_cross_site_requests(tmp_path):
    app = create_app(tmp_path/"reports.db", start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        before = stored_audit(app.state.store, when="2026-01-01T00:00:00+00:00")
        after = stored_audit(app.state.store, when="2026-01-02T00:00:00+00:00")
        body = {"before_audit_id": after.id, "after_audit_id": before.id}
        assert client.post("/api/audit-comparisons", json=body).status_code == 409
        body = {"before_audit_id": before.id, "after_audit_id": after.id}
        assert client.post("/api/audit-comparisons", json=body, headers={"Origin": "https://other.example"}).status_code == 403
        after.origin = "https://other.example"
        app.state.store.save(after)
        assert client.post("/api/audit-comparisons", json=body).status_code == 409


def test_report_includes_review_history_without_private_proposals(tmp_path):
    app = create_app(tmp_path/"reports.db", start_worker=False)
    with TestClient(app, base_url="http://localhost") as client:
        audit = stored_audit(app.state.store, when="2026-01-01T00:00:00+00:00", missing=True)
        issue = audit.issues[0]
        response = client.patch(f"/api/audits/{audit.id}/issues/{issue.id}/disposition",
                                json={"status": "intentional", "reason": "Confirmed for this landing page"})
        assert response.status_code == 200
        output = client.get(f"/api/audits/{audit.id}/report/json").json()
        content = json.loads(output["content"])
        assert "Confirmed for this landing page" in json.dumps(content)
        assert "private_key" not in output["content"] and "fix-artifacts" not in output["content"]
