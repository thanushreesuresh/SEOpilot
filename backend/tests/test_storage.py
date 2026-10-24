from seopilot.models import Audit, Evidence, Issue, Recommendation
from seopilot.storage import Store


def test_persist_queue_and_recover(tmp_path):
    store = Store(tmp_path / "audit.db")
    first = Audit(url="https://example.com/", origin="https://example.com")
    second = Audit(url="https://example.org/", origin="https://example.org")
    assert store.enqueue(first)
    assert not store.enqueue(second, max_pending=1)
    assert store.claim().id == first.id
    assert store.enqueue(second)
    Store(store.path).recover()
    assert store.get(first.id).status == "interrupted"
    assert store.get(second.id).status == "queued"
    assert len(store.history()) == 2


def test_decisions_are_persisted_idempotently(tmp_path):
    store = Store(tmp_path / "audit.db")
    issue = Issue(rule_id="missing_title", title="Missing title", url="https://example.com/",
                  severity="High", category="Metadata", explanation="No title", evidence=[Evidence(field="title", value="")], recommended_fix="Add a title")
    rec = Recommendation(title="Add title", url=issue.url, issue_ids=[issue.id], rationale="No title", priority="High")
    audit = Audit(url=issue.url, status="completed", issues=[issue], recommendations=[rec])
    store.save(audit)
    approved = store.decide(rec.id, "approved")
    assert approved.decided_at
    assert store.decide(rec.id, "approved").decided_at == approved.decided_at
    assert len(store.decisions(audit.id)) == 1
    assert store.decide(rec.id, "rejected").status == "rejected"
    assert len(store.decisions(audit.id)) == 2
    assert Store(store.path).get(audit.id).recommendations[0].status == "rejected"


def test_sql_input_is_data(tmp_path):
    store = Store(tmp_path / "audit.db")
    assert store.get("'; DROP TABLE audits; --") is None
    assert store.history() == []
