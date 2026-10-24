"""Offline sample audit: bundled HTML is parsed and passed through the real rules."""

from .extraction import extract_page
from .models import Audit, Coverage, CrawlDiscovery, DiscoveryProbe, Page, Progress, Recommendation, now
from .rules import analyze, calculate_score, rule_recommendations

ORIGIN = "https://northstar-pottery.example"
# Bump when fixtures or demonstrated evidence change; keep older snapshots intact.
DEMO_REVISION = "2026-10-25.1"
FIXTURES = {
    "/": """<!doctype html><html lang="en"><head>
    <title>Northstar Pottery | Handmade Ceramics</title>
    <link rel="canonical" href="https://northstar-pottery.example/">
    </head><body><h1>Handmade pottery, made in Kochi</h1>
    <p>Northstar Pottery creates handmade ceramic mugs, bowls and tableware in Kochi.
    Visit our studio or join a small-group pottery workshop.</p>
    <h3>Made slowly, used every day</h3><img src="/images/ceramic-bowl.jpg">
    <a href="/workshops">Pottery workshops</a><a href="/about">Our studio</a>
    <a href="/old-collection">Previous collection</a></body></html>""",
    "/workshops": """<!doctype html><html lang="en"><head>
    <title>Northstar Pottery | Handmade Ceramics</title>
    <meta name="description" content="Explore Northstar Pottery in Kochi: handmade ceramics, welcoming studio visits and small-group pottery workshops for curious beginners.">
    </head><body><h1>Pottery workshops in Kochi</h1><h1>Make something by hand</h1>
    <p>Our small-group pottery workshops welcome beginners. Learn to shape a ceramic bowl
    with guidance from the Northstar Pottery studio team.</p><img src="/images/workshop.jpg" alt="">
    <a href="/">Northstar Pottery</a></body></html>""",
    "/about": """<!doctype html><html lang="en"><head><title>About</title>
    <meta name="description" content="Explore Northstar Pottery in Kochi: handmade ceramics, welcoming studio visits and small-group pottery workshops for curious beginners.">
    <link rel="canonical" href="https://northstar-pottery.example/about">
    </head><body><h2>Our Kochi studio</h2><p>Northstar Pottery is a ceramics studio in Kochi.
    We make everyday tableware and teach beginner pottery workshops.</p>
    <a href="/">Home</a></body></html>""",
}


async def build_demo() -> Audit:
    pages = [extract_page(ORIGIN + path, html, depth=0 if path == '/' else 1) for path, html in FIXTURES.items()]
    pages.append(Page(url=ORIGIN + "/old-collection", depth=1, status_code=404, outcome="http_error"))
    audit = Audit(
        url=ORIGIN + "/", origin=ORIGIN, mode="demo", demo_revision=DEMO_REVISION,
        status="completed", ai_status="demo", allow_ai=False, pages=pages,
        business_context="Sample business: a handmade ceramics studio and beginner pottery workshops in Kochi.",
        progress=Progress(stage="completed", visited=4, discovered=4, message="Sample fixture audit complete"),
        coverage=Coverage(attempted=4, assessed=4), completed_at=now(),
        discovery=CrawlDiscovery(robots_state="present", sitemap_state="absent", probes=[
            DiscoveryProbe(kind="robots", url=ORIGIN + "/robots.txt", status_code=200, outcome="present",
                           explanation="Sample fixture: a usable robots.txt text policy."),
            DiscoveryProbe(kind="sitemap", url=ORIGIN + "/sitemap.xml", status_code=404, outcome="absent",
                           explanation="Sample fixture: the inspected location returned HTTP 404."),
        ], notes=["Sample checks only. No HTTP requests or delays were performed."]),
        warnings=["Sample data: bundled HTML fixtures, including a simulated 404. No website or AI provider was contacted."],
    )
    from .rules import RULES_VERSION

    audit.rules_version = RULES_VERSION
    audit.issues = analyze(pages, ORIGIN, robots_state="present", sitemap_state="absent",
                           discovery_evidence={"sitemap": [(ORIGIN + "/sitemap.xml", 404)]})
    audit.score = calculate_score(pages, audit.issues)
    audit.recommendations = rule_recommendations(audit.issues, pages)
    homepage, workshops = pages[:2]
    description_issue = next(issue for issue in audit.issues
                             if issue.rule_id == "description_missing" and homepage.id in issue.page_ids)
    audit.recommendations.extend([
        Recommendation(
            source="demo", kind="description", title="Sample description for the pottery studio", url=homepage.url,
            page_id=homepage.id, issue_ids=[description_issue.id],
            evidence_ids=[f"page:{homepage.id}:text_excerpt"], priority="Medium", basis="inferred",
            rationale="Sample suggestion based on the fixture's handmade tableware, Kochi studio and beginner workshops.",
            suggested_value="Discover handmade ceramic mugs, bowls and tableware from Northstar Pottery in Kochi. Visit the studio or join a beginner pottery workshop.",
        ),
        Recommendation(
            source="demo", kind="title", title="Sample title that distinguishes the workshop page", url=workshops.url,
            page_id=workshops.id, evidence_ids=[f"page:{workshops.id}:headings"], priority="Medium", basis="inferred",
            rationale="The fixture's main heading identifies pottery workshops in Kochi; distinguish this page from the homepage.",
            suggested_value="Beginner Pottery Workshops in Kochi | Northstar Pottery",
        ),
        Recommendation(
            source="demo", kind="keyword", title="Sample inferred keyword theme: beginner pottery workshops", url=workshops.url,
            page_id=workshops.id, evidence_ids=[f"page:{workshops.id}:text_excerpt"], priority="Low", basis="inferred",
            rationale="Inferred from the fixture content. Likely intent: finding a local class suitable for beginners. No search-volume data is available.",
            suggested_value="Inferred themes: pottery workshops in Kochi; beginner pottery class; learn to make a ceramic bowl.",
        ),
    ])
    audit.summary = (
        f"Sample audit: {len(pages)} fixture pages assessed, {len(audit.issues)} evidence-backed rule findings. "
        "Review the missing-page links and metadata first. Optimization examples are curated sample suggestions, not live AI output."
    )
    return audit
