"""Bounded HTML extraction shared by live crawling and the offline sample."""

import re
from collections.abc import Mapping
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .models import Heading, ImageInfo, Page, StructuredDataSummary
from .structured_data import inspect_jsonld

MAX_INPUT = 2 * 1024 * 1024
MAX_HEADINGS = 60
MAX_IMAGES = 200
MAX_LINKS = 500


def _http_url(reference: str, base: str) -> str | None:
    """Resolve text only. Every eventual connection still uses network policy."""
    if any(ord(char) < 32 or ord(char) == 127 for char in reference):
        return None
    try:
        parts = urlsplit(urljoin(base, reference.strip()))
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        hostname = parts.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        if any(char.isspace() for char in hostname) or "\\" in hostname:
            return None
        port = parts.port
        authority = f"[{hostname}]" if ":" in hostname else hostname
        if port is not None and port != (443 if parts.scheme == "https" else 80):
            authority += f":{port}"
        if re.search(r"%(?![0-9a-fA-F]{2})", parts.path + parts.query):
            return None
        path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
        query = quote(parts.query, safe="/?%:@!$&'()*+,;=-._~")
        return urlunsplit((parts.scheme.lower(), authority, path, query, ""))
    except (ValueError, UnicodeError):
        return None


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def extract_page(
    url: str, body: bytes | str, *, status_code: int = 200,
    headers: Mapping[str, str] | None = None, depth: int = 0,
) -> Page:
    normalized = _http_url(url, url)
    if normalized is None:
        raise ValueError("HTML extraction requires an HTTP or HTTPS page URL.")
    headers = {key.lower(): str(value) for key, value in (headers or {}).items()}
    content_type = headers.get("content-type", "text/html")
    page = Page(url=normalized, status_code=status_code, depth=depth, content_type=content_type[:200])
    if status_code >= 400:
        page.outcome = "http_error"
        return page
    if content_type.split(";")[0].strip().lower() not in {"text/html", "application/xhtml+xml"}:
        page.outcome = "non_html"
        return page

    def limited(value: str, limit: int, field: str) -> str:
        if len(value) > limit and field not in page.truncated_fields:
            page.truncated_fields.append(field)
        return value[:limit]

    if len(body) > MAX_INPUT:
        body = body[:MAX_INPUT]
        page.truncated_fields.append("body")
    charset = re.search(r"charset\s*=\s*[\"']?([^;\"'\s]+)", content_type, re.I)
    soup = BeautifulSoup(
        body, "html.parser", from_encoding=charset.group(1) if charset and isinstance(body, bytes) else None,
    )
    if "body" in page.truncated_fields:
        # A clipped script is not evidence of broken website JSON-LD.
        page.structured_data = StructuredDataSummary(blocks=0, truncated=True)
    else:
        page.structured_data = StructuredDataSummary.model_validate(inspect_jsonld(soup))
    if page.structured_data.truncated:
        page.truncated_fields.append("structured_data")
    title = soup.find("title")
    page.title = limited(title.get_text(" ", strip=True) if title else "", 512, "title")

    def record_robots(value: str):
        if len(page.robots) < 10:
            page.robots.append(limited(value, 1000, "robots"))
        elif "robots" not in page.truncated_fields:
            page.truncated_fields.append("robots")

    for meta in soup.find_all("meta"):
        name = str(meta.get("name", "")).casefold()
        if name == "description" and not page.description:
            page.description = limited(str(meta.get("content", "")), 2048, "description")
        if name in {"robots", "googlebot", "bingbot"}:
            value = str(meta.get("content", "")).strip()
            if value:
                record_robots(f"{name}: {value}")
    header_robots = headers.get("x-robots-tag", "").strip()
    if header_robots:
        record_robots(f"X-Robots-Tag: {header_robots}")

    base = normalized
    base_tag = soup.find("base", href=True)
    if base_tag:
        base = _http_url(str(base_tag.get("href", "")), normalized) or normalized

    canonicals = [tag for tag in soup.find_all("link")
                  if "canonical" in [str(value).casefold() for value in tag.get("rel", [])]]
    if len(canonicals) > 5:
        page.truncated_fields.append("canonicals")
    for tag in canonicals[:5]:
        reference = str(tag.get("href", "")).strip()
        # Preserve invalid values as evidence; never fetch a canonical destination.
        page.canonicals.append(limited(urljoin(base, reference) if reference else "", 2048, "canonicals"))

    headings = soup.find_all([f"h{level}" for level in range(1, 7)])
    if len(headings) > MAX_HEADINGS:
        page.truncated_fields.append("headings")
    page.headings = [Heading(level=int(tag.name[1]), text=limited(tag.get_text(" ", strip=True), 512, "headings"))
                     for tag in headings[:MAX_HEADINGS]]

    images = soup.find_all("img")
    if len(images) > MAX_IMAGES:
        page.truncated_fields.append("images")
    for image in images[:MAX_IMAGES]:
        source = str(image.get("src", "")).strip()
        resolved = _http_url(source, base) if source else None
        if source.startswith("data:"):
            resolved = "(inline image; data omitted)"
        page.images.append(ImageInfo(
            src=limited(resolved or "(missing or unsupported image source)", 2048, "images"),
            alt=limited(str(image.get("alt", "")), 512, "images") if image.has_attr("alt") else None,
        ))

    links = set()
    for anchor in soup.find_all("a", href=True):
        reference = str(anchor.get("href", "")).strip()
        if not reference or reference.startswith("#"):
            continue
        resolved = _http_url(reference, base)
        if resolved and len(resolved) <= 2048 and _origin(resolved) == _origin(normalized):
            links.add(resolved)
        if len(links) > MAX_LINKS:
            page.truncated_fields.append("links")
            break
    page.links = sorted(links)[:MAX_LINKS]

    for tag in soup.find_all(["script", "style", "template"]):
        tag.decompose()
    visible = soup.body or soup
    text = re.sub(r"\s+", " ", visible.get_text(" ", strip=True)).strip()
    page.text_excerpt = limited(text, 4000, "text_excerpt")
    return page
