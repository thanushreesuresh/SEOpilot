import copy
import io
import json
import stat
import zipfile

import pytest

from seopilot.ci_validation import MAX_ARCHIVE_BYTES, MAX_REPORT_BYTES, validate_artifact

FIX_ID = "11111111-1111-4111-8111-111111111111"
HEAD = "a" * 40
PATCH = "b" * 64
PNG = b"\x89PNG\r\n\x1a\nfixture-pixels"


def expected():
    return {"fix_run_id": FIX_ID, "head_sha": HEAD, "patch_hash": PATCH, "run_id": "12345", "targets": [{
        "url": "https://example.com/about", "route": "/about", "title": "About Café Works",
        "description": "Learn about our useful services and experienced team.",
        "canonical": ["https://example.com/about"], "robots": ["robots: index, follow"],
    }]}


def report():
    value = expected()
    target = copy.deepcopy(value["targets"][0]) | {
        "status_code": 200, "content_characters": 120, "console_errors": 0, "page_errors": 0,
        "checks": [{"name": name, "status": "passed"} for name in
                   ("http", "title", "description", "content", "console", "page_errors", "canonical", "robots")],
        "screenshot": "screenshots/page-1.png",
    }
    return {"schema_version": 1, "fix_run_id": FIX_ID, "head_sha": HEAD, "patch_hash": PATCH, "run_id": "12345",
            "status": "passed", "checks": [{"name": name, "status": "passed"} for name in
                                            ("install", "build", "render", "lint", "typecheck", "test")],
            "targets": [target]}


def archive(value=None, *, extra=None, screenshots=True):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as result:
        result.writestr("validation.json", json.dumps(value if value is not None else report()))
        if screenshots:
            result.writestr("screenshots/page-1.png", PNG)
        for name, data in (extra or {}).items():
            result.writestr(name, data)
    return stream.getvalue()


def test_exact_commit_proposal_and_all_rendered_measurements_pass():
    result = validate_artifact(archive(), expected())
    assert result["status"] == "passed"
    assert result["screenshots"][0]["bytes"] == len(PNG)
    assert len(result["screenshots"][0]["sha256"]) == 64
    assert result["targets"][0]["title"] == "About Café Works"


@pytest.mark.parametrize("key,value", [("head_sha", "c" * 40), ("patch_hash", "d" * 64),
                                      ("fix_run_id", "22222222-2222-4222-8222-222222222222"), ("run_id", "54321")])
def test_wrong_commit_proposal_and_run_are_rejected(key, value):
    data = report()
    data[key] = value
    assert validate_artifact(archive(data), expected())["status"] == "failed"


def test_failed_build_remains_visible_without_fabricated_page_evidence():
    data = report()
    data["status"] = "failed"
    data["targets"] = []
    data["checks"][1]["status"] = "failed"
    data["checks"][2]["status"] = "failed"
    result = validate_artifact(archive(data, screenshots=False), expected())
    assert result["status"] == "failed"
    assert result["checks"][1] == {"name": "build", "status": "failed"}
    assert result["targets"] == []


def test_missing_optional_scripts_are_explicitly_skipped():
    data = report()
    for item in data["checks"]:
        if item["name"] in {"lint", "typecheck", "test"}:
            item["status"] = "skipped"
    assert validate_artifact(archive(data), expected())["status"] == "passed"
    data["checks"][1]["status"] = "skipped"
    assert validate_artifact(archive(data), expected())["status"] == "failed"


@pytest.mark.parametrize("field,value,check", [("title", "Unexpected title", "title"),
    ("description", "Unapproved text", "description"), ("canonical", [], "canonical"),
    ("robots", ["robots: noindex"], "robots"), ("status_code", 500, "http"),
    ("content_characters", 0, "content"), ("console_errors", 1, "console"), ("page_errors", 1, "page_errors")])
def test_differing_rendered_results_cannot_be_claimed_as_passed(field, value, check):
    data = report()
    data["targets"][0][field] = value
    result = validate_artifact(archive(data), expected())
    assert result["status"] == "failed"
    assert result["targets"] == []
    data["status"] = "failed"
    next(item for item in data["targets"][0]["checks"] if item["name"] == check)["status"] = "failed"
    result = validate_artifact(archive(data), expected())
    assert result["status"] == "failed"
    assert result["targets"][0][field] == value


def test_missing_pages_screenshots_and_duplicate_targets_never_pass():
    data = report()
    data["targets"] = []
    assert validate_artifact(archive(data), expected())["status"] == "failed"
    assert validate_artifact(archive(screenshots=False), expected())["status"] == "failed"
    data = report()
    data["targets"].append(copy.deepcopy(data["targets"][0]))
    assert validate_artifact(archive(data), expected())["status"] == "failed"


@pytest.mark.parametrize("name", ["../secret", "/absolute", "screenshots/../../secret", "screenshots\\evil.png", "source.tsx"])
def test_untrusted_zip_entries_are_never_extracted_or_returned(name):
    result = validate_artifact(archive(extra={name: "PRIVATE_SOURCE_CANARY"}), expected())
    assert result["status"] == "failed"
    assert "PRIVATE_SOURCE_CANARY" not in str(result)


def test_symlink_zip_entry_and_duplicate_report_are_rejected():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as result:
        entry = zipfile.ZipInfo("validation.json")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        result.writestr(entry, "secret")
    assert validate_artifact(stream.getvalue(), expected())["status"] == "failed"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as result:
        result.writestr("validation.json", '{"schema_version":1,"schema_version":1}')
    assert validate_artifact(stream.getvalue(), expected())["status"] == "failed"


def test_archive_and_decompressed_report_limits_are_checked():
    assert validate_artifact(b"a" * (MAX_ARCHIVE_BYTES + 1), expected())["status"] == "failed"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as result:
        result.writestr("validation.json", "a" * (MAX_REPORT_BYTES + 1))
    assert validate_artifact(stream.getvalue(), expected())["status"] == "failed"


def test_missing_and_invalid_artifacts_have_sanitized_states():
    assert validate_artifact(b"", expected())["status"] == "missing"
    assert validate_artifact(b"not-a-zip PRIVATE_SECRET", expected())["status"] == "failed"
    assert "PRIVATE_SECRET" not in str(validate_artifact(b"not-a-zip PRIVATE_SECRET", expected()))
