import asyncio
from urllib.parse import urlsplit

import pytest

from seopilot import crawler
from seopilot.crawler import crawl
from seopilot.models import CrawlOptions
from seopilot.network import NetworkError, NetworkResponse

ORIGIN = "https://example.com"
HTML = b'<html><head><title>Fixture business</title></head><body><h1>Welcome</h1></body></html>'


class FixtureWeb:
    def __init__(self, routes=None):
        self.routes = {
            "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n"),
            "/sitemap.xml": (404, "text/plain", b""),
            "/": (200, "text/html", HTML),
        }
        self.routes.update(routes or {})
        self.calls = []
        self.limits = []

    async def resolve(self, host, port):
        return ["93.184.215.14"]

    async def transport(self, url, address, timeout, max_bytes):
        assert address == "93.184.215.14"
        self.calls.append(url)
        self.limits.append((url, max_bytes))
        value = self.routes.get(urlsplit(url).path, (404, "text/plain", b""))
        if isinstance(value, Exception):
            raise value
        if isinstance(value, NetworkResponse):
            return value
        status, media_type, body = value
        return NetworkResponse(status, {"content-type": media_type}, body)

    async def crawl(self, options=None, progress=None):
        return await crawl(
            ORIGIN, options or CrawlOptions(), progress=progress,
            resolver=self.resolve, transport=self.transport,
        )


@pytest.fixture(autouse=True)
def skip_real_crawl_delays(monkeypatch):
    async def no_wait(seconds):
        pass
    monkeypatch.setattr(crawler.asyncio, "sleep", no_wait)


@pytest.mark.asyncio
async def test_end_to_end_crawl_extracts_actual_html_and_probe_evidence():
    web = FixtureWeb({
        "/": (200, "text/html", b'<title>Local pottery</title><h1>Ceramics</h1><a href="/about">About</a>'),
        "/about": (200, "text/html", b'<title>About us</title><h1>Our studio</h1>'),
    })
    updates = []

    async def progress(pages, discovered):
        updates.append((len(pages), discovered))

    result = await web.crawl(progress=progress)
    assert [page.title for page in result.pages] == ["Local pottery", "About us"]
    assert result.coverage.assessed == 2
    assert result.coverage.failed == 0
    assert updates == [(1, 2), (2, 2)]
    assert result.robots_state == "present"
    assert result.sitemap_state == "absent"
    assert result.discovery_evidence == {
        "robots": [(ORIGIN + "/robots.txt", 200)], "sitemap": [(ORIGIN + "/sitemap.xml", 404)],
    }


@pytest.mark.asyncio
async def test_robots_disallow_is_not_fetched_and_specific_allow_wins():
    web = FixtureWeb({
        "/robots.txt": (200, "text/plain", b"User-agent: *\nDisallow: /private\nAllow: /private/public\n"),
        "/": (200, "text/html", b'<a href="/private">No</a><a href="/private/public">Yes</a>'),
        "/private/public": (200, "text/html", HTML),
    })
    result = await web.crawl()
    assert ORIGIN + "/private" not in web.calls
    assert ORIGIN + "/private/public" in web.calls
    assert result.coverage.blocked == 1
    assert any(page.outcome == "blocked" for page in result.pages)


@pytest.mark.asyncio
async def test_named_user_agent_policy_and_delay_are_honored(monkeypatch):
    delays = []

    async def record_wait(seconds):
        delays.append(seconds)

    monkeypatch.setattr(crawler.asyncio, "sleep", record_wait)
    web = FixtureWeb({
        "/robots.txt": (200, "text/plain", b"User-agent: *\nDisallow: /\nUser-agent: SEOPilot\nAllow: /\nCrawl-delay: 1.5\n"),
    })
    result = await web.crawl()
    assert result.pages[0].outcome == "html"
    assert len(delays) == 2
    assert all(1.4 < value <= 1.5 for value in delays)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
async def test_unverified_robots_policy_fails_closed(status):
    web = FixtureWeb({"/robots.txt": (status, "text/plain", b"error")})
    result = await web.crawl()
    assert web.calls == [ORIGIN + "/robots.txt"]
    assert result.robots_state == "unknown"
    assert result.coverage.assessed == 0
    assert result.coverage.blocked == 1
    assert result.warnings


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 410])
async def test_verified_absent_robots_allows_bounded_crawl(status):
    web = FixtureWeb({"/robots.txt": (status, "text/plain", b"not found")})
    result = await web.crawl()
    assert result.robots_state == "absent"
    assert result.pages[0].outcome == "html"
    assert result.discovery_evidence["robots"] == [(ORIGIN + "/robots.txt", status)]


@pytest.mark.asyncio
@pytest.mark.parametrize("media_type,body", [
    ("text/html", b"<html><title>Oops</title></html>"),
    ("text/plain", b"<!DOCTYPE html><html>Oops</html>"),
    ("application/json", b'{"error":"bad"}'),
])
async def test_html_or_json_error_disguised_as_successful_robots_does_not_allow_crawl(media_type, body):
    web = FixtureWeb({"/robots.txt": (200, media_type, body)})
    result = await web.crawl()
    assert result.robots_state == "unknown"
    assert result.coverage.blocked == 1
    assert web.calls == [ORIGIN + "/robots.txt"]


@pytest.mark.asyncio
async def test_empty_robots_file_is_a_valid_allow_policy():
    web = FixtureWeb({"/robots.txt": (200, "text/plain", b"")})
    assert (await web.crawl()).pages[0].outcome == "html"


@pytest.mark.asyncio
async def test_robots_network_failure_does_not_fetch_content():
    web = FixtureWeb({"/robots.txt": NetworkError("The website request timed out.")})
    result = await web.crawl()
    assert web.calls == [ORIGIN + "/robots.txt"]
    assert result.pages[0].outcome == "blocked"
    assert result.robots_state == "unknown"


@pytest.mark.asyncio
async def test_page_and_depth_limits_report_unchecked_coverage():
    web = FixtureWeb({
        "/": (200, "text/html", b'<a href="/a">A</a><a href="/b">B</a>'),
        "/a": (200, "text/html", HTML),
        "/b": (200, "text/html", HTML),
    })
    limited = await web.crawl(CrawlOptions(page_limit=2))
    assert len(limited.pages) == 2
    assert limited.coverage.unchecked == 1
    assert limited.coverage.truncated
    web.calls.clear()
    shallow = await web.crawl(CrawlOptions(max_depth=0))
    assert len(shallow.pages) == 1
    assert shallow.coverage.unchecked == 2
    assert ORIGIN + "/a" not in web.calls


@pytest.mark.asyncio
async def test_external_and_fragment_links_are_not_crawled_and_duplicates_are_deduplicated():
    web = FixtureWeb({
        "/": (200, "text/html", b'<a href="https://other.com/">External</a><a href="/a#one">A</a><a href="/a#two">A</a>'),
        "/a": (200, "text/html", HTML),
    })
    result = await web.crawl()
    assert len(result.pages) == 2
    assert web.calls.count(ORIGIN + "/a") == 1
    assert all(url.startswith(ORIGIN) for url in web.calls)


@pytest.mark.asyncio
async def test_redirect_into_robots_disallowed_page_is_blocked_before_target_request():
    web = FixtureWeb({
        "/robots.txt": (200, "text/plain", b"User-agent: *\nDisallow: /private\n"),
        "/": NetworkResponse(302, {"location": "/private"}, b""),
    })
    result = await web.crawl()
    assert result.pages[0].outcome == "blocked"
    assert ORIGIN + "/private" not in web.calls


@pytest.mark.asyncio
async def test_same_origin_redirects_are_normalized_without_duplicate_final_page_evidence():
    web = FixtureWeb({
        "/": (200, "text/html", b'<a href="/old">Old</a><a href="/new">New</a>'),
        "/old": NetworkResponse(301, {"location": "/new"}, b""),
        "/new": (200, "text/html", HTML),
    })
    result = await web.crawl()
    assert len([page for page in result.pages if page.url == ORIGIN + "/new"]) == 1


@pytest.mark.asyncio
async def test_http_errors_non_html_and_failed_pages_preserve_truthful_classification():
    web = FixtureWeb({
        "/": (200, "text/html", b'<a href="/bad">Bad</a><a href="/file">File</a><a href="/timeout">Timeout</a>'),
        "/bad": (404, "text/html", b'<title>Ignore error page metadata</title>secret error body'),
        "/file": (200, "application/pdf", b"pdf"),
        "/timeout": NetworkError("The website request timed out."),
    })
    result = await web.crawl()
    bad = next(page for page in result.pages if page.url.endswith("/bad"))
    assert bad.outcome == "http_error" and bad.status_code == 404
    assert bad.title == bad.text_excerpt == ""
    assert result.coverage.assessed == 2
    assert result.coverage.failed == 1
    assert result.coverage.unchecked == 1


@pytest.mark.asyncio
async def test_not_modified_is_not_assessed_as_html():
    web = FixtureWeb({"/": (304, "text/html", HTML)})
    result = await web.crawl()
    assert result.pages[0].outcome == "non_html"
    assert result.coverage.assessed == 0


@pytest.mark.asyncio
async def test_sitemap_namespace_is_recognized_but_html_and_entity_documents_are_not():
    valid = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></urlset>'
    web = FixtureWeb({"/sitemap.xml": (200, "application/xml", valid)})
    assert (await web.crawl()).sitemap_state == "present"
    web.routes["/sitemap.xml"] = (200, "text/html", HTML)
    assert (await web.crawl()).sitemap_state == "unknown"
    web.routes["/sitemap.xml"] = (200, "application/xml", b'<!DOCTYPE urlset [<!ENTITY x "x">]><urlset>&x;</urlset>')
    assert (await web.crawl()).sitemap_state == "unknown"


@pytest.mark.asyncio
async def test_external_sitemap_declarations_are_not_fetched_or_reported_missing():
    web = FixtureWeb({"/robots.txt": (200, "text/plain", b"User-agent: *\nSitemap: https://other.com/map.xml\n")})
    result = await web.crawl()
    assert result.sitemap_state == "unknown"
    assert all(url.startswith(ORIGIN) for url in web.calls)


@pytest.mark.asyncio
async def test_large_sitemap_candidate_set_does_not_create_false_absence():
    body = b"User-agent: *\n" + b"".join(f"Sitemap: {ORIGIN}/map-{index}.xml\n".encode() for index in range(21))
    web = FixtureWeb({"/robots.txt": (200, "text/plain", body)})
    result = await web.crawl()
    assert result.sitemap_state == "unknown"
    assert len(result.discovery_evidence["sitemap"]) == 3


@pytest.mark.asyncio
async def test_sitemap_robots_exclusion_leaves_unknown_state():
    web = FixtureWeb({"/robots.txt": (200, "text/plain", b"User-agent: *\nDisallow: /sitemap.xml\n")})
    result = await web.crawl()
    assert result.sitemap_state == "unknown"
    assert ORIGIN + "/sitemap.xml" not in web.calls


@pytest.mark.asyncio
async def test_total_http_request_budget_is_hard_and_retains_partial_pages(monkeypatch):
    monkeypatch.setattr(crawler, "MAX_REQUESTS", 3)
    web = FixtureWeb({"/": (200, "text/html", b'<a href="/next">Next</a>')})
    result = await web.crawl()
    assert len(web.calls) == 3
    assert result.coverage.truncated
    assert result.pages[0].outcome == "html"
    assert any("request limit" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_discovery_budget_is_hard(monkeypatch):
    monkeypatch.setattr(crawler, "MAX_DISCOVERED", 3)
    body = b"".join(f'<a href="/page-{index}">Page</a>'.encode() for index in range(10))
    web = FixtureWeb({"/": (200, "text/html", body)})
    updates = []

    async def progress(pages, discovered):
        updates.append(discovered)

    result = await web.crawl(progress=progress)
    assert max(updates) == 3
    assert len(result.pages) == 3
    assert result.coverage.truncated


@pytest.mark.asyncio
async def test_robots_parser_byte_limit_is_not_lowered_by_page_limit_setting():
    web = FixtureWeb({"/robots.txt": (200, "text/plain", b"# note\n" * 1000 + b"User-agent: *\nAllow: /\n")})
    result = await web.crawl(CrawlOptions(response_bytes=1024))
    assert result.pages[0].outcome == "html"
    assert web.limits[0] == (ORIGIN + "/robots.txt", 512 * 1024)


@pytest.mark.asyncio
async def test_extraction_truncation_is_visible_in_coverage():
    web = FixtureWeb({"/": (200, "text/html", b"<h1>Fixture</h1>" + b"text " * 1000)})
    result = await web.crawl()
    assert "text_excerpt" in result.pages[0].truncated_fields
    assert result.coverage.truncated
    assert any("extracted" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_excessive_crawl_delay_stops_instead_of_ignoring_policy():
    web = FixtureWeb({"/robots.txt": (200, "text/plain", b"User-agent: *\nCrawl-delay: 10000\n")})
    result = await web.crawl()
    assert result.coverage.blocked == 1
    assert web.calls == [ORIGIN + "/robots.txt"]


@pytest.mark.asyncio
async def test_total_wall_time_budget_cancels_a_stalled_hop(monkeypatch):
    web = FixtureWeb()
    original_transport = web.transport
    cancelled = asyncio.Event()

    async def stalled(url, address, timeout, max_bytes):
        if url == ORIGIN + "/":
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        return await original_transport(url, address, timeout, max_bytes)

    # A shorter test-only model copy exercises the same deadline without five seconds of waiting.
    options = CrawlOptions().model_copy(update={"total_seconds": 0.02})
    result = await crawl(ORIGIN, options, resolver=web.resolve, transport=stalled)
    assert cancelled.is_set()
    assert result.coverage.truncated and result.coverage.failed == 1
    assert any("time budget" in warning for warning in result.warnings)


@pytest.mark.asyncio
@pytest.mark.parametrize("media_type", ["application/pdf", "image/png", "application/octet-stream", "application/xml"])
async def test_unsupported_robots_media_cannot_become_empty_allow_policy(media_type):
    web = FixtureWeb({"/robots.txt": (200, media_type, b"binary or non-policy content")})
    result = await web.crawl()
    assert result.robots_state == "unknown"
    assert result.coverage.blocked == 1
    assert web.calls == [ORIGIN + "/robots.txt"]


@pytest.mark.asyncio
@pytest.mark.parametrize("media_type", ["", "text/plain; charset=utf-8", "text/x-robots"])
async def test_usable_robots_text_media_is_supported(media_type):
    web = FixtureWeb({"/robots.txt": (200, media_type, b"User-agent: *\nAllow: /\n")})
    result = await web.crawl()
    assert result.robots_state == "present"
    assert result.pages[0].outcome == "html"
