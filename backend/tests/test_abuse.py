from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from seopilot.abuse import canonical_identity, client_identity
from seopilot.app import create_app
from seopilot.models import Audit
from seopilot.settings import Settings
from seopilot.storage import Store


def audit(index=0):
    return Audit(url=f"https://example.com/{index}", origin="https://example.com")


def test_atomic_daily_quota_concurrency_restart_and_private_identity(tmp_path):
    path = tmp_path / "quota.db"
    stores = [Store(path) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda index: stores[index].admit_audit(audit(index), "198.51.100.2", at=100000), range(8)))
    assert sum(reason == "created" for _, reason, _ in results) == 3
    restored = Store(path)
    assert restored.quota("198.51.100.2", at=100001)["remaining"] == 0
    assert restored.admit_audit(audit(20), "198.51.100.2", at=100001)[1] == "daily"
    assert restored.quota("198.51.100.3", at=100001)["remaining"] == 3
    with restored.connection() as db:
        stored = db.execute("SELECT identity FROM admissions").fetchall()
        assert all("198.51.100.2" not in row[0] and len(row[0]) == 64 for row in stored)
    assert restored.quota("198.51.100.2", at=186400)["remaining"] == 3


def test_duplicate_requests_share_one_job_and_recent_complete_result(tmp_path):
    store = Store(tmp_path / "quota.db")
    first = audit()
    assert store.admit_audit(first, "peer", at=100000)[1] == "created"
    reused, reason, quota = store.admit_audit(audit(), "peer", at=100001)
    assert reused.id == first.id and reason == "reused" and quota["used"] == 1
    first.status = "completed"
    store.save(first)
    assert store.admit_audit(audit(), "peer", at=100899)[0].id == first.id
    assert store.admit_audit(audit(), "peer", at=100900)[1] == "created"
    assert store.admit_audit(audit(), "different-peer", at=100901)[1] == "created"
    opted_out = audit()
    opted_out.allow_ai = False
    assert store.admit_audit(opted_out, "peer", at=100902)[1] == "created"


def test_full_queue_does_not_charge_and_failed_admissions_remain_charged(tmp_path):
    store = Store(tmp_path / "quota.db")
    first = audit()
    store.enqueue(first)
    assert store.admit_audit(audit(1), "peer", max_pending=1)[1] == "queue"
    assert store.quota("peer")["used"] == 0
    first.status = "failed"
    store.save(first)
    admitted, _, _ = store.admit_audit(audit(1), "peer")
    admitted.status = "failed"
    store.save(admitted)
    assert store.quota("peer")["used"] == 1
    assert store.admit_audit(audit(1), "peer")[1] == "created"


def test_ai_call_budget_atomic_global_lifetime_and_restart(tmp_path):
    path = tmp_path / "calls.db"
    store = Store(path)
    audits = [audit(index) for index in range(8)]
    for item in audits:
        store.save(item)
    stores = [Store(path) for _ in audits]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda index: stores[index].reserve_ai_call(audits[index].id, 3), range(8)))
    assert sum(results) == 3
    assert Store(path).ai_calls_remaining(3) == 0
    assert not Store(path).reserve_ai_call(audits[0].id, 3)
    separate = Store(tmp_path / "lifetime.db")
    separate.save(audits[0])
    assert separate.reserve_ai_call(audits[0].id, 20)
    assert separate.reserve_ai_call(audits[0].id, 20)
    assert not separate.reserve_ai_call(audits[0].id, 20)


def test_canonical_ip_rotation_and_untrusted_forwarding():
    assert canonical_identity("::ffff:198.51.100.4") == "198.51.100.4"
    assert canonical_identity("2001:db8:1234:5678::1") == canonical_identity("2001:db8:1234:5678::abcd")
    assert canonical_identity("nonsense") == "unknown"
    def request(peer, headers):
        return SimpleNamespace(client=SimpleNamespace(host=peer), headers=Headers(headers),
                               app=SimpleNamespace(state=SimpleNamespace(proxy_token="a" * 64)))
    assert client_identity(request("198.51.100.4", {"x-forwarded-for": "1.1.1.1"})) == "198.51.100.4"
    assert client_identity(request("127.0.0.1", {"x-seopilot-proxy-token": "a" * 64,
                                               "x-seopilot-client-ip": "198.51.100.4"})) == "198.51.100.4"
    for peer, headers in [
        ("198.51.100.4", {"x-seopilot-proxy-token": "a" * 64, "x-seopilot-client-ip": "1.1.1.1"}),
        ("127.0.0.1", {"x-seopilot-proxy-token": "wrong", "x-seopilot-client-ip": "1.1.1.1"}),
        ("127.0.0.1", {"x-seopilot-proxy-token": "é" * 64, "x-seopilot-client-ip": "1.1.1.1"}),
        ("127.0.0.1", {"x-seopilot-client-ip": "1.1.1.1"}),
        ("127.0.0.1", {"x-seopilot-proxy-token": "a" * 64, "x-seopilot-client-ip": "bad"}),
    ]:
        with pytest.raises(HTTPException):
            client_identity(request(peer, headers))
    duplicate = request("127.0.0.1", {})
    duplicate.headers = Headers(raw=[(b"x-seopilot-proxy-token", b"a" * 64),
                                    (b"x-seopilot-proxy-token", b"a" * 64),
                                    (b"x-seopilot-client-ip", b"1.1.1.1")])
    with pytest.raises(HTTPException):
        client_identity(duplicate)


def test_api_quota_headers_forgery_restart_demo_and_optout(tmp_path):
    path = tmp_path / "api.db"
    with TestClient(create_app(path, start_worker=False), base_url="http://localhost") as client:
        assert client.get("/api/usage").json()["remaining"] == 3
        assert client.post("/api/audits", json={"url": "http://127.0.0.1/"}).status_code == 422
        for index in range(3):
            response = client.post("/api/audits", json={"url": f"https://example.com/{index}", "allow_ai": False})
            assert response.status_code == 202 and response.json()["allow_ai"] is False
            assert response.headers["RateLimit-Remaining"] == str(2 - index)
        reused = client.post("/api/audits", json={"url": "https://example.com/0", "allow_ai": False})
        assert reused.status_code == 202 and reused.headers["X-Audit-Reused"] == "true"
        response = client.post("/api/audits", json={"url": "https://example.com/fourth"}, headers={"X-Forwarded-For": "8.8.8.8"})
        assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
        assert client.get("/api/usage").json()["remaining"] == 0
        assert client.get("/api/usage", headers={"X-SEOPilot-Client-IP": "8.8.8.8"}).status_code == 403
        first = client.post("/api/demo-audits", json={}).json()
        second = client.post("/api/demo-audits", json={}).json()
        assert first["id"] == second["id"] and first["mode"] == "demo"
    with TestClient(create_app(path, start_worker=False), base_url="http://localhost") as client:
        assert client.get("/api/usage").json()["remaining"] == 0
        assert client.post("/api/audits", json={"url": "https://example.com/fifth"}).status_code == 429


@pytest.mark.parametrize("address,proxied", [("127.0.0.1", False), ("::1", False),
                                            ("::ffff:127.0.0.1", True)])
def test_local_unlimited_survives_exhaustion_and_restart_without_resetting_history(tmp_path, address, proxied):
    path = tmp_path / "local.db"
    store = Store(path)
    identity = canonical_identity(address)
    for index in range(3):
        item, reason, _ = store.admit_audit(audit(index), identity)
        assert reason == "created"
        item.status = "completed"
        store.save(item)
    before_ids = {item.id for item in store.history()}
    config = Settings(local_unlimited_audits=True, ai_daily_call_limit=0)
    app = create_app(path, start_worker=False, settings=config)
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1" if proxied else address, 50000)) as client:
        headers = ({"x-seopilot-proxy-token": app.state.proxy_token, "x-seopilot-client-ip": address}
                   if proxied else {})
        usage = client.get("/api/usage", headers=headers).json()
        assert usage["unlimited"] and usage["used"] == 3
        assert usage["limit"] is None and usage["remaining"] is None
        assert usage["reset_at"] is None and usage["retry_after"] == 0
        # More than both the old daily limit and ten-request burst guard.
        for index in range(12):
            response = client.post("/api/audits", headers=headers,
                                   json={"url": f"https://example.com/local-{index}", "allow_ai": False})
            assert response.status_code == 202
            assert "RateLimit-Limit" not in response.headers
            saved = app.state.store.get(response.json()["id"])
            saved.status = "completed"
            app.state.store.save(saved)
        reused = client.post("/api/audits", headers=headers,
                             json={"url": "https://example.com/local-0", "allow_ai": False})
        assert reused.status_code == 202 and reused.headers["X-Audit-Reused"] == "true"
        assert not app.state.store.reserve_ai_call(saved.id, 0)
    restored = Store(path)
    assert restored.quota(identity)["used"] == 15
    assert before_ids.issubset({item.id for item in restored.history()})
    with restored.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM ai_calls").fetchone()[0] == 0
    with TestClient(create_app(path, start_worker=False, settings=config), base_url="http://localhost",
                    client=(address, 50000)) as client:
        assert client.get("/api/usage").json()["unlimited"]
        assert client.post("/api/audits", json={"url": "https://example.com/after-restart", "allow_ai": False}).status_code == 202


@pytest.mark.parametrize("proxied", [False, True])
def test_unlimited_setting_keeps_remote_clients_limited_and_rejects_spoofed_localhost(tmp_path, proxied):
    app = create_app(tmp_path / "remote.db", start_worker=False, settings=Settings(local_unlimited_audits=True))
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1" if proxied else "198.51.100.4", 50000)) as client:
        headers = {"x-forwarded-for": "127.0.0.1", "x-real-ip": "::1"}
        if proxied:
            headers.update({"x-seopilot-proxy-token": app.state.proxy_token, "x-seopilot-client-ip": "198.51.100.4"})
        usage = client.get("/api/usage", headers=headers).json()
        assert not usage["unlimited"] and usage["remaining"] == 3
        for index in range(3):
            assert client.post("/api/audits", headers=headers,
                               json={"url": f"https://example.com/{index}", "allow_ai": False}).status_code == 202
        assert client.post("/api/audits", headers=headers,
                           json={"url": "https://example.com/fourth", "allow_ai": False}).status_code == 429
        assert client.get("/api/usage", headers={"x-seopilot-client-ip": "127.0.0.1"}).status_code == 403


def test_unlimited_local_queue_capacity_still_applies(tmp_path):
    app = create_app(tmp_path / "capacity.db", start_worker=False, settings=Settings(local_unlimited_audits=True))
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000)) as client:
        for index in range(5):
            assert client.post("/api/audits", json={"url": f"https://example.com/{index}", "allow_ai": False}).status_code == 202
        response = client.post("/api/audits", json={"url": "https://example.com/full", "allow_ai": False})
        assert response.status_code == 429 and "queue is full" in response.json()["detail"]
        usage = client.get("/api/usage").json()
        assert usage["unlimited"] and usage["used"] == 5
