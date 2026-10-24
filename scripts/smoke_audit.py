"""Exercise the real local API with one bounded public page and current server configuration."""

import argparse
import json
import time

import httpx

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--url", default="https://example.com/")
args = parser.parse_args()

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=15, trust_env=False) as client:
    response = client.post("/api/audits", json={
        "url": args.url,
        "options": {"page_limit": 1, "max_depth": 0, "total_seconds": 20, "timeout_seconds": 8},
    })
    response.raise_for_status()
    audit_id = response.json()["id"]
    deadline = time.monotonic() + 110
    while time.monotonic() < deadline:
        response = client.get(f"/api/audits/{audit_id}")
        response.raise_for_status()
        audit = response.json()
        if audit["status"] not in {"queued", "crawling", "analyzing", "reviewing"}:
            print(json.dumps({
                "id": audit_id, "status": audit["status"], "mode": audit["mode"],
                "coverage": audit["coverage"], "score": audit["score"]["value"],
                "ai_status": audit["ai_status"], "issues": len(audit["issues"]),
                "titles": [page["title"] for page in audit["pages"]], "warnings": audit["warnings"],
            }, indent=2))
            raise SystemExit(0 if audit["coverage"]["assessed"] else 1)
        time.sleep(0.5)
raise SystemExit("The audit did not finish before the smoke-test deadline.")
