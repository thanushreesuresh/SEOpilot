from seopilot.extraction import extract_page


def test_extracts_metadata_headers_and_distinguishes_missing_alt():
    page = extract_page("https://example.com/start", """
    <html><head><title>Example services</title>
    <meta name="description" content="Useful services">
    <meta name="robots" content="index, follow"><meta name="googlebot" content="noindex">
    <link rel="CANONICAL" href="/preferred"></head><body>
    <h1>Our services</h1><h3>Details</h3>
    <img src="/missing.jpg"><img src="/decorative.jpg" alt="">
    <a href="/about#team">About</a><a href="/about#staff">Duplicate target</a>
    <a href="//external.example/ignore">External</a><a href="javascript:alert(1)">Unsafe</a>
    <script>secret script body</script><style>hidden styles</style>
    <template>hidden template</template><p>Visible useful text</p></body></html>
    """, headers={"X-Robots-Tag": "nofollow"}, depth=2)
    assert page.title == "Example services" and page.description == "Useful services"
    assert page.canonicals == ["https://example.com/preferred"]
    assert [heading.level for heading in page.headings] == [1, 3]
    assert [image.alt for image in page.images] == [None, ""]
    assert page.links == ["https://example.com/about"]
    assert any("googlebot: noindex" == value for value in page.robots)
    assert any("nofollow" in value for value in page.robots)
    assert "Visible useful text" in page.text_excerpt
    assert "secret script" not in page.text_excerpt and "hidden template" not in page.text_excerpt
    assert page.depth == 2


def test_base_resolution_does_not_fetch_or_reinterpret_external_links_as_internal():
    page = extract_page("https://example.com/", """
    <base href="https://cdn.example/"><a href="relative">External relative link</a>
    <a href="https://example.com/retained">Internal absolute link</a>
    <link rel="canonical" href="/preferred">
    """)
    assert page.links == ["https://example.com/retained"]
    assert page.canonicals == ["https://cdn.example/preferred"]


def test_relative_base_normalizes_links_and_discards_credentials_or_bad_schemes():
    page = extract_page("https://EXAMPLE.com:443/start", """
    <base href="/section/"><a href="../about?q=hello world#team">About</a>
    <a href="https://user:password@example.com/private">Credentials</a>
    <a href="mailto:hello@example.com">Mail</a><a href="/bad%escape">Malformed encoding</a>
    """)
    assert page.url == "https://example.com/start"
    assert page.links == ["https://example.com/about?q=hello%20world"]


def test_http_error_and_non_html_do_not_produce_body_findings():
    error = extract_page("https://example.com/missing", "<h1>Server error body</h1>", status_code=404)
    assert error.outcome == "http_error" and error.headings == []
    binary = extract_page("https://example.com/document", b"not html", headers={"Content-Type": "application/pdf"})
    assert binary.outcome == "non_html" and binary.title == ""


def test_truncates_bounded_content_and_records_limits():
    html = (
        "<title>" + "t" * 1000 + "</title><meta name='description' content='" + "d" * 3000 + "'>"
        + "<body>" + "<h2>Heading</h2>" * 80 + "<img src='/photo'>" * 250
        + "".join(f"<a href='/page/{i}'>Link</a>" for i in range(600)) + "x" * 5000 + "</body>"
    )
    page = extract_page("https://example.com/", html)
    assert len(page.title) == 512 and len(page.description) == 2048
    assert len(page.headings) == 60 and len(page.images) == 200 and len(page.links) == 500
    assert len(page.text_excerpt) == 4000
    assert set(page.truncated_fields) >= {"title", "description", "headings", "images", "links", "text_excerpt"}


def test_empty_or_non_http_canonical_is_preserved_for_rule_evidence():
    page = extract_page("https://example.com/", '<link rel="canonical" href=""><link rel="canonical" href="mailto:x@example.com">')
    assert page.canonicals == ["", "mailto:x@example.com"]


def test_declared_encoding_is_respected():
    page = extract_page("https://example.com/", "<title>Café</title>".encode("windows-1252"),
                        headers={"Content-Type": "text/html; charset=windows-1252"})
    assert page.title == "Café"


def test_extra_indexing_directives_cannot_silently_disappear():
    html = '<meta name="robots" content="index, follow">' * 10
    page = extract_page("https://example.com/", html+'<meta name="googlebot" content="noindex">')
    assert len(page.robots) == 10
    assert "robots" in page.truncated_fields


def test_header_overflow_also_marks_indexing_evidence_incomplete():
    html = '<meta name="robots" content="index, follow">' * 10
    page = extract_page("https://example.com/", html, headers={"X-Robots-Tag": "noindex"})
    assert len(page.robots) == 10
    assert "robots" in page.truncated_fields
