import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from seopilot.fix_models import FixRun, Project
from seopilot.models import Audit
from seopilot.storage import Store


def setup(tmp_path):
    store = Store(tmp_path / "test.db")
    audit = Audit(url="https://example.org/", origin="https://example.org")
    store.admit_audit(audit, "192.0.2.1")
    project = store.fixes.connect(Project(name="Pilot", production_origin=audit.origin, installation_id=1,
        repository_id=2, repository_owner="owner", repository_name="site", base_branch="main"))
    return store, project, audit


def run_for(project, audit):
    return FixRun(project_id=project.id, audit_id=audit.id, repository_id=2, base_branch="main", base_sha="a"*40,
        patch_hash="b"*64, expires_at=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat(),
        targets=[], changed_files=[], changed_lines=0)


def test_reopening_existing_workflow_schema_preserves_mapping_and_counters(tmp_path):
    store, project, audit = setup(tmp_path)
    assert store.reserve_ai_call(audit.id, 20)
    reopened = Store(store.path)
    assert reopened.get(audit.id).url == audit.url
    assert reopened.quota("192.0.2.1")["used"] == 1
    assert reopened.ai_calls_remaining(20) == 19
    assert reopened.fixes.project(project.id).repository_id == 2
    with reopened.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3


def test_one_active_run_and_publication_reservations_are_durable(tmp_path):
    store, project, audit = setup(tmp_path)
    one = run_for(project, audit)
    store.fixes.create(one)
    with pytest.raises(ValueError, match="active"):
        store.fixes.create(run_for(project, audit))
    assert store.fixes.reserve_publication(one.id)
    assert store.fixes.reserve_publication(one.id)
    one.status = "cancelled"
    store.fixes.save(one)
    two = run_for(project, audit)
    store.fixes.create(two)
    assert store.fixes.reserve_publication(two.id)
    two.status = "cancelled"
    store.fixes.save(two)
    three = run_for(project, audit)
    store.fixes.create(three)
    assert not Store(store.path).fixes.reserve_publication(three.id)


def test_retention_and_delete_remove_private_source_but_keep_history(tmp_path):
    store, project, audit = setup(tmp_path)
    run = run_for(project, audit)
    store.fixes.create(run)
    store.fixes.write_artifact(run.id, {"source": "PRIVATE_CANARY"})
    assert store.fixes.artifact(run)["source"] == "PRIVATE_CANARY"
    run.expires_at = (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    store.fixes.save(run)
    store.fixes.cleanup()
    saved = store.fixes.get(run.id)
    assert saved.status == "expired" and saved.source_purged
    assert not list(store.fixes.artifacts.glob("*.json"))
    with pytest.raises(ValueError):
        store.fixes.artifact(saved)
    with pytest.raises(ValueError):
        store.fixes.write_artifact("../../secret", {})


def test_connection_conflict_and_foreign_key(tmp_path):
    store, project, audit = setup(tmp_path)
    with pytest.raises(ValueError, match="Disconnect"):
        store.fixes.connect(project)
    run = run_for(project, audit)
    run.audit_id = "forged"
    with pytest.raises(sqlite3.IntegrityError):
        store.fixes.create(run)


def test_proposals_are_frozen_and_retention_is_not_limited_to_ui_history(tmp_path):
    store, project, audit = setup(tmp_path)
    oldest = run_for(project, audit)
    oldest.expires_at = "2000-01-01T00:00:00+00:00"
    oldest.status = "cancelled"
    store.fixes.create(oldest)
    store.fixes.write_artifact(oldest.id, {"private": "SOURCE_CANARY"})
    for _ in range(101):
        run = run_for(project, audit)
        run.status = "cancelled"
        store.fixes.create(run)
    assert len(store.fixes.history()) == 100
    store.fixes.cleanup()
    assert store.fixes.get(oldest.id).source_purged
    assert not store.fixes._artifact_path(oldest.id).exists()
    run.patch_hash = "0"*64
    with pytest.raises(ValueError, match="immutable"):
        store.fixes.save(run)


def test_crash_leftover_temporary_source_obeys_retention(tmp_path):
    import os

    store, _, _ = setup(tmp_path)
    store.fixes.artifacts.mkdir()
    path = store.fixes.artifacts / "interrupted.tmp"
    path.write_text("PRIVATE_SOURCE_CANARY", encoding="utf-8")
    os.utime(path, (1, 1))
    store.fixes.cleanup()
    assert not path.exists()
