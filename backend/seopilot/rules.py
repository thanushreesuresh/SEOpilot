"""Evidence-based SEO diagnostics. The score is a heuristic, never a ranking forecast."""

import re
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlsplit

from .models import Evidence, Issue, Page, Recommendation, Score

POINTS = {"Critical": 20, "High": 10, "Medium": 5, "Low": 2}


@dataclass(frozen=True)
class RuleThresholds:
    """Editorial character-count heuristics; configure when calling analyze()."""

    title_min: int = 15
    title_max: int = 60
    description_min: int = 50
    description_max: int = 160

    def __post_init__(self):
        if not (0 < self.title_min < self.title_max and 0 < self.description_min < self.description_max):
            raise ValueError("Character thresholds must have a positive minimum below their maximum.")


def _assessed(page: Page) -> bool:
    return page.status_code is not None and (
        page.outcome == "html" and 200 <= page.status_code < 300
        or page.outcome == "http_error" and 400 <= page.status_code < 600
    )


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def analyze(
    pages: list[Page], origin: str, robots_state: str = "unknown", sitemap_state: str = "unknown",
    *, thresholds: RuleThresholds | None = None,
    discovery_evidence: dict[str, list[tuple[str, int]]] | None = None,
) -> list[Issue]:
    thresholds = thresholds or RuleThresholds()
    issues: list[Issue] = []

    def add(page, rule_id, title, severity, category, explanation, fix, evidence, *, group=None, is_site=False):
        issues.append(Issue(
            rule_id=rule_id, title=title, url=page.url if page else origin,
            page_ids=[p.id for p in (group or [page])] if page else [], severity=severity,
            category=category, explanation=explanation, recommended_fix=fix,
            evidence=[Evidence(field=field, value=str(value)[:2048]) for field, value in evidence], is_site=is_site,
        ))

    assessed = [p for p in pages if _assessed(p)]
    html = [p for p in assessed if p.outcome == "html"]
    known_status = {urldefrag(p.url)[0]: p.status_code for p in assessed}
    for page in assessed:
        if page.outcome == "http_error":
            add(page, "http_error", "Page returned an HTTP error", "High", "Crawlability",
                "The server returned an error response. Its content was not evaluated as a normal page.",
                "Restore the intended page, update links, or return a suitable intentional status.",
                [("status_code", page.status_code)])
            continue
        if urlsplit(page.url).scheme == "http":
            add(page, "non_https", "Page uses HTTP", "Medium", "Security",
                "This response used an unencrypted connection.",
                "Serve the page over HTTPS and redirect its HTTP address to the HTTPS version.", [("url", page.url)])
        for field, minimum, maximum, label, missing_severity in (
            ("title", thresholds.title_min, thresholds.title_max, "title", "High"),
            ("description", thresholds.description_min, thresholds.description_max, "meta description", "Medium"),
        ):
            value = getattr(page, field).strip()
            if not value and 'body' not in page.truncated_fields:
                add(page, f"{field}_missing", f"Missing {label}", missing_severity, "Metadata",
                    f"No non-empty {label} was found in the fetched HTML.",
                    f"Write a unique, descriptive {label} that accurately reflects this page.", [(field, "(missing or empty)")])
            elif value and (len(value) < minimum or len(value) > maximum):
                direction = "short" if len(value) < minimum else "long"
                add(page, f"{field}_{direction}", f"Review {direction} {label}", "Low", "Metadata",
                    f"The extracted {label} has {len(value)} characters. The {minimum}–{maximum} range is an editorial heuristic; "
                    "display lengths vary and this is not a Google ranking rule.",
                    f"Review the {label} for clarity and useful detail; change its length only if that improves it.",
                    [(field, value), ("character_count", len(value))])
        h1 = [h for h in page.headings if h.level == 1]
        if not h1 and not {'headings', 'body'} & set(page.truncated_fields):
            add(page, "h1_missing", "No H1 heading found", "Medium", "Content",
                "The fetched HTML has no H1 to identify the page's main subject.",
                "Add a descriptive main heading if the page is intended to have one.", [("h1_count", 0)])
        elif len(h1) > 1:
            add(page, "h1_multiple", "Review multiple H1 headings", "Low", "Content",
                "Multiple H1 headings may be intentional. Review whether the main subject and structure are clear.",
                "Use a clear main heading and appropriate subheadings for this page's structure.",
                [("h1_headings", " | ".join(h.text for h in h1))])
        skips = [f"H{a.level} → H{b.level}: {b.text}" for a, b in zip(page.headings, page.headings[1:])
                 if b.level > a.level + 1]
        if skips:
            add(page, "heading_hierarchy", "Heading levels skip a step", "Low", "Content",
                "Some headings jump over a level, which may make the document structure harder to navigate.",
                "Review heading levels to reflect the nesting of sections.", [("heading_transition", s) for s in skips[:10]])
        missing_alt = [image.src for image in page.images if image.alt is None]
        if missing_alt:
            add(page, "image_alt_missing", "Images lack an alt attribute", "Low", "Accessibility",
                f"{len(missing_alt)} inspected images have no alt attribute. Empty alt text is allowed for decorative images.",
                "Describe meaningful images; add an empty alt attribute to purely decorative images.",
                [("image_src", src) for src in missing_alt[:10]])
        if not page.canonicals and 'body' not in page.truncated_fields:
            add(page, "canonical_missing", "No canonical tag found", "Low", "Indexability",
                "No canonical tag was found. A canonical can clarify the preferred URL when duplicate versions exist.",
                "Consider a self-referencing canonical for the preferred public URL; it is not required for every page.",
                [("canonical", "(missing)")])
        elif len(page.canonicals) > 1:
            add(page, "canonical_multiple", "Multiple canonical tags found", "Medium", "Indexability",
                "Multiple canonical tags can give conflicting preferred-URL signals.",
                "Choose one appropriate preferred URL and emit a single canonical tag.",
                [("canonical", c) for c in page.canonicals[:5]])
        elif page.canonicals:
            canonical = page.canonicals[0]
            try:
                resolved = urljoin(page.url, canonical)
                parsed = urlsplit(resolved)
                valid = (bool(canonical.strip()) and parsed.scheme in {"http", "https"}
                         and bool(parsed.hostname) and not parsed.username
                         and not any(character.isspace() for character in parsed.hostname))
            except ValueError:
                valid = False
                resolved = canonical
            if not valid:
                add(page, "canonical_invalid", "Canonical URL needs correction", "Medium", "Indexability",
                    "The canonical value is not a valid public HTTP or HTTPS URL reference.",
                    "Set the canonical to the correct absolute HTTP or HTTPS URL.", [("canonical", canonical)])
            elif urldefrag(resolved)[0].rstrip("/") != urldefrag(page.url)[0].rstrip("/"):
                add(page, "canonical_nonself", "Review canonical pointing to another page", "Low", "Indexability",
                    "The canonical points to another URL. This can be intentional; confirm that it is the preferred equivalent.",
                    "Keep this canonical if intentional; otherwise point it to the preferred version of this page.",
                    [("canonical", canonical), ("page_url", page.url)])
        tokens = {token for value in page.robots for token in re.split(r"[\s,;:]+", value.casefold())}
        if tokens & {"noindex", "none"}:
            add(page, "indexing_restricted", "Page requests exclusion from indexing", "Low", "Indexability",
                "A noindex directive was observed. Excluding a page from indexing may be intentional.",
                "Confirm the page's intended indexing policy before changing any directive.",
                [("robots", value) for value in page.robots[:5]])
        broken = sorted({link for link in page.links if known_status.get(urldefrag(link)[0]) in {404, 410}
                         and urlsplit(link).netloc == urlsplit(origin).netloc})
        if broken:
            add(page, "broken_internal_link", "Internal links lead to missing pages", "High", "Links",
                "These inspected internal targets returned HTTP 404 or 410. Unchecked targets are not classified as broken.",
                "Update or remove links to missing pages, or restore the intended destinations.",
                [("broken_target", f"{link} (HTTP {known_status[urldefrag(link)[0]]})") for link in broken[:10]])

    for field, label in (("title", "title"), ("description", "meta description")):
        groups = defaultdict(list)
        for page in html:
            value = _normalized(getattr(page, field))
            if value and field not in page.truncated_fields and 'body' not in page.truncated_fields:
                groups[value].append(page)
        for group in groups.values():
            if len(group) > 1:
                add(group[0], f"{field}_duplicate", f"Pages share the same {label}", "Medium", "Metadata",
                    f"{len(group)} audited pages have the same normalized {label}. Confirm whether they represent distinct content.",
                    f"Write a distinct {label} for each distinct page; keep duplicates only when they are intentional.",
                    [(field, getattr(group[0], field)), ("affected_urls", "\n".join(p.url for p in group))], group=group)
    for name, state in (("robots", robots_state), ("sitemap", sitemap_state)):
        if state == "absent":
            inspected = (discovery_evidence or {}).get(name, [])
            observations = [("inspected_url", f"{url} (HTTP {status})") for url, status in inspected]
            if not observations:
                observations = [("discovery_state", "Caller confirmed absence; request details not supplied."),
                                ("inspected_scope", origin)]
            add(None, f"{name}_absent", "No robots.txt found" if name == "robots" else "No sitemap found in inspected locations",
                "Low", "Discovery",
                "The inspected default or declared locations were confirmed absent. Other locations may exist; absence alone is not a ranking penalty.",
                "Consider publishing a suitable robots.txt." if name == "robots" else "Consider publishing an XML sitemap and declaring its URL in robots.txt.",
                observations, is_site=True)
    return sorted(issues, key=lambda issue: (-POINTS[issue.severity], issue.url, issue.rule_id))


def calculate_score(pages: list[Page], issues: list[Issue]) -> Score:
    assessed = {p.id: p for p in pages if _assessed(p)}
    if not assessed:
        return Score()
    penalties = {page_id: 0 for page_id in assessed}
    site: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        points = POINTS[issue.severity]
        if issue.is_site:
            site[issue.rule_id] = max(site.get(issue.rule_id, 0), points)
            continue
        for page_id in issue.page_ids:
            key = (issue.rule_id, page_id)
            if page_id in penalties and key not in seen:
                penalties[page_id] += points
                seen.add(key)
    for page_id, page in assessed.items():
        penalties[page_id] = 100 if page.outcome == "http_error" else min(100, penalties[page_id])
    value = max(0, min(100, round(100 - sum(penalties.values()) / len(assessed) - min(20, sum(site.values())))))
    return Score(value=value, assessed_pages=len(assessed))


def rule_recommendations(issues: list[Issue], pages: list[Page]) -> list[Recommendation]:
    page_ids = {page.id for page in pages}
    results = []
    for issue in issues:
        kind = "technical"
        if issue.rule_id.startswith("title_"):
            kind = "title"
        elif issue.rule_id.startswith("description_"):
            kind = "description"
        elif issue.rule_id.startswith(("h1_", "heading_")):
            kind = "heading"
        results.append(Recommendation(
            title=issue.title, kind=kind, url=issue.url,
            page_id=issue.page_ids[0] if len(issue.page_ids) == 1 and issue.page_ids[0] in page_ids else None,
            issue_ids=[issue.id], evidence_ids=[e.id for e in issue.evidence], rationale=issue.recommended_fix,
            priority=issue.severity, source="rule", basis="observed",
        ))
    return results
