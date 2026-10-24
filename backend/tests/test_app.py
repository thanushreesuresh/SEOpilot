from fastapi.testclient import TestClient

from seopilot.app import create_app


def test_local_api_guards_and_health(tmp_path):
    with TestClient(create_app(tmp_path / "audit.db", start_worker=False)) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/audits").json() == []
        assert client.get("/api/audits/missing").status_code == 404
        assert client.post("/api/demo-audits", json={}, headers={"Origin": "https://attacker.example"}).status_code == 403
        assert client.post("/api/demo-audits", content="{}").status_code == 415
        assert client.post("/api/demo-audits", json={"padding": "x" * 17000}).status_code == 413
        assert client.get("/api/health", headers={"Host": "attacker.example"}).status_code == 400


def test_schema_describes_shared_types(tmp_path):
    schema = create_app(tmp_path / "audit.db", start_worker=False).openapi()
    assert "Audit" in schema["components"]["schemas"]
    assert "Recommendation" in schema["components"]["schemas"]
    assert not (tmp_path / "audit.db").exists()
