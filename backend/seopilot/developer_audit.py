"""Explicit local developer audits. No HTTP exemption, dotenv loading or paid AI."""

import argparse
import asyncio
import json
from functools import partial
from pathlib import Path

from .models import Audit, CrawlOptions, Progress, now
from .network import normalize_url, origin_of
from .runner import _process_audit, execute
from .settings import BACKEND_ROOT, Settings
from .storage import Store


async def run_developer_audit(url: str, database: Path, options: CrawlOptions, reason: str, *, dns: str = "system") -> Audit:
    url = normalize_url(url)
    if not reason.strip() or len(reason) > 160 or any(ord(char) < 32 for char in reason):
        raise ValueError("Provide a nonempty developer-run reason of at most 160 characters.")
    if dns not in {"system", "google"}:
        raise ValueError("Choose system or google DNS.")
    audit = Audit(url=url, origin=origin_of(url), options=options, allow_ai=False,
                  business_context=f"Local developer audit (AI disabled; DNS={dns}): " + reason.strip(),
                  progress=Progress(limit=options.page_limit))
    store = Store(database)
    store.start_developer_audit(audit)
    try:
        network_options = {}
        if dns == "google":
            from .developer_dns import resolve_google

            network_options["resolver"] = resolve_google
        await _process_audit(audit, store, partial(execute, settings=Settings(ai_enabled=False), **network_options))
    except asyncio.CancelledError:
        audit.status = "interrupted"
        audit.progress.stage = "interrupted"
        audit.progress.message = "Local developer audit interrupted; partial evidence retained."
        audit.completed_at = now()
        store.save(audit)
        raise
    except Exception:
        audit.status = "failed"
        audit.progress.stage = "failed"
        audit.progress.message = "Local developer audit failed; retained evidence may be incomplete."
        audit.completed_at = now()
        store.save(audit)
    return store.get(audit.id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--database", type=Path, default=BACKEND_ROOT / ".data" / "seopilot.db")
    parser.add_argument("--pages", type=int, default=15)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--dns", choices=("system", "google"), default="system")
    args = parser.parse_args(argv)
    try:
        options = CrawlOptions(page_limit=args.pages, max_depth=args.depth)
        audit = asyncio.run(run_developer_audit(args.url, args.database, options, args.reason, dns=args.dns))
    except ValueError:
        print(json.dumps({"error": "Invalid URL, crawl settings, reason, or available audit capacity."}))
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"error": "Developer audit interrupted; retained evidence is in history."}))
        return 130
    except Exception:
        print(json.dumps({"error": "Developer audit could not start. Check local storage and dependencies."}))
        return 1
    print(json.dumps({"audit_id": audit.id, "url": audit.url, "status": audit.status,
                      "assessed_pages": audit.coverage.assessed, "score": audit.score.value,
                      "findings": len(audit.issues), "ai_status": audit.ai_status,
                      "public_admission_charged": False}))
    return 0 if audit.status in {"completed", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
