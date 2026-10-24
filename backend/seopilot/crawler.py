"""Sequential, robots-aware crawling with explicit coverage and hard resource bounds."""

import asyncio
import math
import time
import xml.etree.ElementTree as ET
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from urllib.parse import urljoin

from protego import Protego

from .extraction import extract_page
from .models import Coverage, CrawlOptions, Page
from .network import NetworkError, NetworkPolicyError, Resolver, Transport, fetch, normalize_url, origin_of

MAX_REQUESTS = 60
MAX_DISCOVERED = 500
POLICY_BYTES = 512 * 1024
ROBOT_NAME = "SEOPilot"
ProgressCallback = Callable[[list[Page], int], Awaitable[None]]


@dataclass
class CrawlResult:
    pages: list[Page] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)
    robots_state: str = "unknown"
    sitemap_state: str = "unknown"
    discovery_evidence: dict[str, list[tuple[str, int]]] = field(default_factory=lambda: {"robots": [], "sitemap": []})


class CrawlBudgetError(NetworkError):
    pass


def _is_sitemap(body: bytes) -> bool:
    text = body.decode("utf-8-sig", errors="replace")
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        return False
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, ValueError):
        return False
    return root.tag.rsplit("}", 1)[-1] in {"urlset", "sitemapindex"}


async def crawl(
    url: str,
    options: CrawlOptions,
    progress: ProgressCallback | None = None,
    *,
    resolver: Resolver | None = None,
    transport: Transport | None = None,
) -> CrawlResult:
    seed = normalize_url(url)
    origin = origin_of(seed)
    result = CrawlResult()
    discovered: dict[str, int] = {seed: 0}
    visited: set[str] = set()
    final_urls: set[str] = set()
    queue = deque([(seed, 0)])
    request_count = 0
    last_request: float | None = None
    delay = options.delay_ms / 1000
    active_url: str | None = None
    truncated = False

    def warn(message: str) -> None:
        if message not in result.warnings and len(result.warnings) < 30:
            result.warnings.append(message)

    async def before_request(target: str) -> None:
        nonlocal request_count, last_request
        if request_count >= MAX_REQUESTS:
            raise CrawlBudgetError("The total HTTP request limit was reached.")
        if last_request is not None:
            await asyncio.sleep(max(0.0, last_request + delay - time.monotonic()))
        request_count += 1
        last_request = time.monotonic()

    async def get(target: str, *, policy: Protego | None = None, limit: int | None = None):
        return await fetch(
            target,
            allowed_origin=origin,
            timeout=options.timeout_seconds,
            max_bytes=limit or options.response_bytes,
            resolver=resolver,
            transport=transport,
            before_request=before_request,
            permit_url=(lambda candidate: policy.can_fetch(candidate, ROBOT_NAME)) if policy is not None else None,
        )

    async def notify() -> None:
        if progress is not None:
            await progress(list(result.pages), len(discovered))

    async def inspect_sitemap(policy: Protego) -> None:
        candidates: list[str] = []
        uncertain = False
        declared_sitemaps = list(policy.sitemaps)
        if len(declared_sitemaps) > 20:
            uncertain = True
        for declared in declared_sitemaps[:20]:
            try:
                candidate = normalize_url(urljoin(origin + "/", declared))
            except ValueError:
                uncertain = True
                continue
            if origin_of(candidate) != origin:
                uncertain = True
                continue
            if candidate not in candidates:
                candidates.append(candidate)
        fallback = origin + "/sitemap.xml"
        if fallback not in candidates:
            candidates.append(fallback)
        if len(candidates) > 3:
            uncertain = True
        candidates = candidates[:3]
        all_absent = bool(candidates)
        for candidate in candidates:
            if not policy.can_fetch(candidate, ROBOT_NAME):
                uncertain = True
                all_absent = False
                continue
            try:
                response = await get(candidate, policy=policy, limit=POLICY_BYTES)
            except CrawlBudgetError:
                raise
            except NetworkError:
                uncertain = True
                all_absent = False
                continue
            result.discovery_evidence["sitemap"].append((response.url, response.status_code))
            if 200 <= response.status_code < 300 and _is_sitemap(response.body):
                result.sitemap_state = "present"
                return
            if response.status_code not in {404, 410}:
                all_absent = False
                uncertain = True
        if all_absent and not uncertain:
            result.sitemap_state = "absent"

    async def run() -> None:
        nonlocal delay, active_url, truncated
        try:
            robots = await get(origin + "/robots.txt", limit=POLICY_BYTES)
        except CrawlBudgetError:
            raise
        except NetworkError as error:
            warn("robots.txt could not be verified; no pages were crawled.")
            result.pages.append(Page(url=seed, outcome="blocked", error=str(error), content_type=""))
            visited.add(seed)
            await notify()
            return
        result.discovery_evidence["robots"].append((robots.url, robots.status_code))
        if robots.status_code in {404, 410}:
            result.robots_state = "absent"
            policy = Protego.parse("")
        elif 200 <= robots.status_code < 300:
            media_type = robots.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            prefix = robots.body[:4096].lower()
            if (
                media_type not in {"", "text/plain", "text/x-robots"}
                or b"<html" in prefix or b"<!doctype html" in prefix
            ):
                warn("robots.txt returned an unusable policy response; no pages were crawled.")
                result.pages.append(Page(url=seed, outcome="blocked", content_type="", error="robots.txt was not a usable crawl policy."))
                visited.add(seed)
                await notify()
                return
            result.robots_state = "present"
            policy = Protego.parse(robots.body.decode("utf-8-sig", errors="replace"))
        else:
            warn(f"robots.txt returned HTTP {robots.status_code}; crawling was conservatively stopped.")
            result.pages.append(
                Page(url=seed, outcome="blocked", error="The website's crawl policy could not be verified.", content_type="")
            )
            visited.add(seed)
            await notify()
            return
        robot_delay = policy.crawl_delay(ROBOT_NAME)
        if robot_delay is not None:
            if not math.isfinite(robot_delay) or robot_delay >= options.total_seconds:
                result.pages.append(
                    Page(url=seed, outcome="blocked", error="robots.txt requires a delay beyond this audit's time budget.")
                )
                visited.add(seed)
                warn("The robots.txt crawl delay exceeds the audit time budget.")
                await notify()
                return
            delay = max(delay, robot_delay)
        await inspect_sitemap(policy)
        while queue and len(result.pages) < options.page_limit:
            candidate, depth = queue.popleft()
            if candidate in visited:
                continue
            visited.add(candidate)
            active_url = candidate
            if not policy.can_fetch(candidate, ROBOT_NAME):
                result.pages.append(
                    Page(url=candidate, depth=depth, outcome="blocked", error="robots.txt disallows this URL.", content_type="")
                )
                active_url = None
                await notify()
                continue
            try:
                response = await get(candidate, policy=policy)
            except CrawlBudgetError:
                raise
            except NetworkPolicyError as error:
                result.pages.append(Page(url=candidate, depth=depth, outcome="blocked", error=str(error), content_type=""))
            except NetworkError as error:
                result.pages.append(Page(url=candidate, depth=depth, outcome="error", error=str(error), content_type=""))
            else:
                if response.url in final_urls:
                    active_url = None
                    await notify()
                    continue
                final_urls.add(response.url)
                visited.add(response.url)
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if response.status_code >= 400:
                    page = Page(
                        url=response.url,
                        depth=depth,
                        status_code=response.status_code,
                        outcome="http_error",
                        content_type=content_type,
                        error=f"The website returned HTTP {response.status_code}.",
                    )
                elif not 200 <= response.status_code < 300 or content_type not in {"text/html", "application/xhtml+xml"}:
                    page = Page(
                        url=response.url, depth=depth, status_code=response.status_code,
                        outcome="non_html", content_type=content_type,
                    )
                else:
                    page = extract_page(
                        response.url, response.body, status_code=response.status_code, headers=response.headers, depth=depth,
                    )
                result.pages.append(page)
                if page.truncated_fields:
                    truncated = True
                    warn("Some extracted page fields reached their size limits; findings use the retained evidence only.")
                if page.outcome == "html":
                    for link in page.links:
                        try:
                            link = normalize_url(link)
                        except ValueError:
                            continue
                        if origin_of(link) != origin or link in discovered:
                            continue
                        if len(discovered) >= MAX_DISCOVERED:
                            truncated = True
                            warn("The discovered URL limit was reached; additional links were not queued.")
                            break
                        discovered[link] = depth + 1
                        if depth < options.max_depth:
                            queue.append((link, depth + 1))
                        else:
                            truncated = True
                            warn("The crawl depth limit left some discovered URLs unchecked.")
            active_url = None
            await notify()
        if queue:
            truncated = True
            warn("The page limit left some discovered URLs unchecked.")

    try:
        async with asyncio.timeout(options.total_seconds):
            await run()
    except (TimeoutError, CrawlBudgetError) as error:
        truncated = True
        message = "The crawl time budget was reached." if isinstance(error, TimeoutError) else str(error)
        warn(message)
        if active_url is not None:
            result.pages.append(Page(url=active_url, outcome="error", content_type="", error=message))
        elif not result.pages:
            result.pages.append(Page(url=seed, outcome="error", content_type="", error=message))
    result.coverage = Coverage(
        attempted=len(result.pages),
        assessed=sum(page.outcome in {"html", "http_error"} for page in result.pages),
        blocked=sum(page.outcome == "blocked" for page in result.pages),
        failed=sum(page.outcome == "error" for page in result.pages),
        unchecked=sum(candidate not in visited for candidate in discovered)
        + sum(page.outcome == "non_html" for page in result.pages),
        truncated=truncated,
    )
    return result


