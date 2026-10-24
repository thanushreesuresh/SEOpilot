"""Read bounded, untrusted GitHub validation artifacts without extracting files.

The caller must first authorize the Actions workflow ID and exact head SHA using
GitHub's run metadata. Artifact contents alone cannot establish their producer.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import stat
import zipfile
import zlib
from pathlib import PurePosixPath

MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_EXPANDED_BYTES = 10 * 1024 * 1024
MAX_REPORT_BYTES = 128 * 1024
MAX_SCREENSHOT_BYTES = 2 * 1024 * 1024
REQUIRED_CHECKS = {"install", "build", "render"}
OPTIONAL_CHECKS = {"lint", "typecheck", "test"}
TARGET_CHECKS = {"http", "title", "description", "content", "console", "page_errors", "canonical", "robots"}
IDENTIFIER = re.compile(r"^[0-9a-f-]{36}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
HASH = re.compile(r"^[0-9a-f]{64}$")
SCREENSHOT = re.compile(r"^screenshots/page-[1-3]\.png$")


def _failed(summary: str) -> dict:
    return {"status": "failed", "summary": summary, "checks": [], "targets": [], "screenshots": []}


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _checks(value: object, names: set[str], *, optional: set[str] | None = None) -> bool:
    if not isinstance(value, list) or len(value) != len(names):
        return False
    seen = set()
    for check in value:
        if not isinstance(check, dict) or set(check) != {"name", "status"}:
            return False
        name, status = check["name"], check["status"]
        if not isinstance(name, str) or name not in names or name in seen:
            return False
        if status not in {"passed", "failed", "skipped"} or (status == "skipped" and name not in (optional or set())):
            return False
        seen.add(name)
    return seen == names


def _safe_text(value: object, limit: int) -> bool:
    return isinstance(value, str) and len(value) <= limit and not any(ord(char) < 32 for char in value)


def _string_list(value: object) -> bool:
    return isinstance(value, list) and len(value) <= 10 and all(_safe_text(item, 2048) for item in value)


def validate_artifact(data: bytes, expected: dict) -> dict:
    """Return a sanitized result bound to a proposal and its exact commit.

    ``expected`` requires fix_run_id, patch_hash, head_sha and the frozen targets.
    Each target contains url, route, title, description, canonical and robots.
    An optional run_id binds the producer run too. Never return raw artifact text.
    """
    if not data:
        return {"status": "missing", "summary": "Validation artifact is missing.",
                "checks": [], "targets": [], "screenshots": []}
    if len(data) > MAX_ARCHIVE_BYTES:
        return _failed("Validation artifact exceeded the size limit.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= 8 or sum(item.file_size for item in entries) > MAX_EXPANDED_BYTES:
                return _failed("Validation artifact exceeded the entry limit.")
            files = {}
            for item in entries:
                path = PurePosixPath(item.filename)
                if (path.is_absolute() or ".." in path.parts or "\\" in item.filename
                        or item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16)):
                    return _failed("Validation artifact contains an unsafe entry.")
                if item.is_dir():
                    if item.filename != "screenshots/":
                        return _failed("Validation artifact contains an unexpected directory.")
                    continue
                if item.filename in files or not (item.filename == "validation.json" or SCREENSHOT.fullmatch(item.filename)):
                    return _failed("Validation artifact contains an unexpected file.")
                limit = MAX_REPORT_BYTES if item.filename == "validation.json" else MAX_SCREENSHOT_BYTES
                if item.file_size > limit:
                    return _failed("Validation artifact exceeded the file limit.")
                # read() verifies ZIP CRC; the size bound is checked before decompression.
                files[item.filename] = archive.read(item)
        if "validation.json" not in files:
            return _failed("Validation report is missing.")
        report = json.loads(files["validation.json"].decode("utf-8"), object_pairs_hook=_unique_json)
        return _validate_report(report, files, expected)
    except (ValueError, TypeError, UnicodeError, zipfile.BadZipFile, zlib.error, OSError, RuntimeError, KeyError,
            RecursionError):
        return _failed("Validation artifact could not be verified.")


def _validate_report(report: object, files: dict[str, bytes], expected: dict) -> dict:
    required = {"schema_version", "fix_run_id", "patch_hash", "head_sha", "run_id", "status", "checks", "targets"}
    if not isinstance(report, dict) or set(report) != required or report["schema_version"] != 1:
        return _failed("Validation report has an unsupported format.")
    if not (IDENTIFIER.fullmatch(str(report["fix_run_id"])) and HASH.fullmatch(str(report["patch_hash"]))
            and SHA.fullmatch(str(report["head_sha"])) and re.fullmatch(r"[1-9][0-9]{0,19}", str(report["run_id"]))):
        return _failed("Validation report has invalid identifiers.")
    for name in ("fix_run_id", "patch_hash", "head_sha"):
        if report[name] != expected.get(name):
            return _failed("Validation report does not match this proposal and commit.")
    if "run_id" in expected and str(report["run_id"]) != str(expected["run_id"]):
        return _failed("Validation report does not match the selected workflow run.")
    if report["status"] not in {"passed", "failed"} or not _checks(
        report["checks"], REQUIRED_CHECKS | OPTIONAL_CHECKS, optional=OPTIONAL_CHECKS,
    ):
        return _failed("Validation report has incomplete build checks.")
    targets, wanted = report["targets"], expected.get("targets")
    if not isinstance(wanted, list) or not 1 <= len(wanted) <= 3 or not isinstance(targets, list):
        return _failed("Validation report has an invalid page set.")
    if (not targets and report["status"] == "failed"
            and any(check["status"] == "failed" and check["name"] in REQUIRED_CHECKS for check in report["checks"])):
        return {"status": "failed", "summary": "Hosted build or rendering checks failed before pages were assessed.",
                "checks": report["checks"], "targets": [], "screenshots": []}
    if len(targets) != len(wanted):
        return _failed("Validation report did not assess every proposed page.")
    by_url = {item["url"]: item for item in wanted}
    if len(by_url) != len(wanted):
        return _failed("Validation report has an ambiguous page set.")
    seen, screenshots = set(), []
    target_keys = {"url", "route", "title", "description", "canonical", "robots", "status_code",
                   "content_characters", "console_errors", "page_errors", "checks", "screenshot"}
    for target in targets:
        if not isinstance(target, dict) or set(target) != target_keys or not _safe_text(target["url"], 2048):
            return _failed("Validation report has an invalid page result.")
        url = target["url"]
        if url not in by_url or url in seen:
            return _failed("Validation report assessed unexpected pages.")
        seen.add(url)
        proposal = by_url[url]
        if not (_safe_text(target["route"], 2048) and _safe_text(target["title"], 500)
                and _safe_text(target["description"], 2000) and _string_list(target["canonical"])
                and _string_list(target["robots"]) and _checks(target["checks"], TARGET_CHECKS)):
            return _failed("Validation report has invalid rendered metadata.")
        integers = [target[key] for key in ("status_code", "content_characters", "console_errors", "page_errors")]
        if any(type(value) is not int or not 0 <= value <= 1_000_000 for value in integers):
            return _failed("Validation report has invalid page measurements.")
        screenshot = target["screenshot"]
        if not isinstance(screenshot, str) or not SCREENSHOT.fullmatch(screenshot) or screenshot not in files:
            return _failed("Validation report is missing a page screenshot.")
        pixels = files[screenshot]
        if not pixels.startswith(b"\x89PNG\r\n\x1a\n") or any(item["path"] == screenshot for item in screenshots):
            return _failed("Validation report has an invalid page screenshot.")
        screenshots.append({"path": screenshot, "sha256": hashlib.sha256(pixels).hexdigest(), "bytes": len(pixels)})
        conditions = {
            "http": 200 <= target["status_code"] < 300,
            "title": target["title"] == proposal.get("title"),
            "description": target["description"] == proposal.get("description"),
            "content": target["content_characters"] >= 40,
            "console": target["console_errors"] == 0,
            "page_errors": target["page_errors"] == 0,
            "canonical": target["canonical"] == proposal.get("canonical"),
            "robots": target["robots"] == proposal.get("robots"),
        }
        if target["route"] != proposal.get("route"):
            return _failed("Validation report changed a proposed route.")
        if any((check["status"] == "passed") != conditions[check["name"]] for check in target["checks"]):
            return _failed("Validation report contradicts its rendered measurements.")
    checks_passed = all(check["status"] != "failed" for check in report["checks"])
    pages_passed = all(check["status"] == "passed" for target in targets for check in target["checks"])
    status = "passed" if checks_passed and pages_passed else "failed"
    if report["status"] != status:
        return _failed("Validation report contradicts its check results.")
    return {"status": status, "summary": "Hosted checks passed." if status == "passed" else "Hosted checks failed.",
            "checks": report["checks"], "targets": targets, "screenshots": screenshots}
