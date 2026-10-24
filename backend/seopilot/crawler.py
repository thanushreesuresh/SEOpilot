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
from .models import Coverage, CrawlDiscovery, CrawlOptions, DiscoveryProbe, Page
from .network import NetworkError, NetworkPolicyError, Resolver, Transport, fetch, normalize_url, origin_of

MAX_REQUESTS = 60
MAX_DISCOVERED = 500
POLICY_BYTES = 512 * 1024
ROBOT_NAME = "SEOPilot"
ProgressCallback = Callable[[list[Page], int, CrawlDiscovery], Awaitable[None]]


@dataclass
class CrawlResult:
    pages: list[Page] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)
    robots_state: str = "unknown"
    sitemap_state: str = "unknown"
    discovery_evidence: dict[str, list[tuple[str, int]]] = field(default_factory=lambda: {"robots": [], "sitemap": []})
    probes: list[DiscoveryProbe] = field(default_factory=list)
    request_attempts: int = 0
    effective_delay_seconds: float = 0.75
    discovery_notes: list[str] = field(default_factory=list)

    def discovery_snapshot(self) -> CrawlDiscovery:
        return CrawlDiscovery(
            robots_state=self.robots_state, sitemap_state=self.sitemap_state,
            probes=[probe.model_copy() for probe in self.probes], request_attempts=self.request_attempts,
            effective_delay_seconds=self.effective_delay_seconds, notes=list(self.discovery_notes),
        )


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
    targets: list[str] | None = None,
) -> CrawlResult:
    seed = normalize_url(url)
    origin = origin_of(seed)
    result = CrawlResult(effective_delay_seconds=options.delay_ms / 1000)
    seeds = [normalize_url(item) for item in targets] if targets else [seed]
    if not seeds or len(seeds) > 3 or any(origin_of(item) != origin for item in seeds):
        raise ValueError("Verification requires one to three URLs on the original origin.")
    discovered: dict[str, int] = dict.fromkeys(seeds, 0)
    visited: set[str] = set()
    final_urls: set[str] = set()
    queue = deque([(item, 0) for item in seeds])
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
        result.request_attempts = request_count
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
            await progress(list(result.pages), len(discovered), result.discovery_snapshot())

    def note(message: str) -> None:
        if message not in result.discovery_notes:
            result.discovery_notes.append(message)

    def probe(kind, url, outcome, explanation, status=None) -> None:
        result.probes.append(DiscoveryProbe(
            kind=kind, url=url, outcome=outcome, explanation=explanation, status_code=status,
        ))

    async def inspect_sitemap(policy: Protego) -> None:
        candidates: list[str] = []
        uncertain = False
        declared_sitemaps = list(policy.sitemaps)
        if len(declared_sitemaps) > 20:
            uncertain = True
            note("Only the first 20 sitemap declarations were considered.")
        for declared in declared_sitemaps[:20]:
            try:
                candidate = normalize_url(urljoin(origin + "/", declared))
            except ValueError:
                uncertain = True
                note("An unsafe or invalid sitemap declaration was skipped.")
                continue
            if origin_of(candidate) != origin:
                uncertain = True
                note("An external-origin sitemap declaration was skipped.")
                continue
            if candidate not in candidates:
                candidates.append(candidate)
        fallback = origin + "/sitemap.xml"
        if fallback not in candidates:
            candidates.append(fallback)
        if len(candidates) > 3:
            uncertain = True
            note("Only the first three same-origin sitemap locations were inspected.")
        candidates = candidates[:3]
        all_absent = bool(candidates)
        for candidate in candidates:
            if not policy.can_fetch(candidate, ROBOT_NAME):
                uncertain = True
                all_absent = False
                probe("sitemap", candidate, "blocked", "robots.txt disallows this sitemap location; no request was made.")
                await notify()
                continue
            try:
                response = await get(candidate, policy=policy, limit=POLICY_BYTES)
            except CrawlBudgetError:
                raise
            except NetworkError:
                uncertain = True
                all_absent = False
                probe("sitemap", candidate, "unknown", "A protected network request failed; sitemap presence is unknown.")
                await notify()
                continue
            result.discovery_evidence["sitemap"].append((response.url, response.status_code))
            if 200 <= response.status_code < 300 and _is_sitemap(response.body):
                result.sitemap_state = "present"
                probe("sitemap", response.url, "present", "Recognized a sitemap XML root. Listed URLs and indexing were not verified.", response.status_code)
                await notify()
                return
            if response.status_code in {404, 410}:
                probe("sitemap", response.url, "absent", "This inspected location returned HTTP 404 or 410.", response.status_code)
            else:
                probe("sitemap", response.url, "unknown", "The response did not establish a usable sitemap XML root.", response.status_code)
            if response.status_code not in {404, 410}:
                all_absent = False
                uncertain = True
            await notify()
        if all_absent and not uncertain:
            result.sitemap_state = "absent"
        await notify()

    async def run() -> None:
        nonlocal delay, active_url, truncated
        try:
            robots = await get(origin + "/robots.txt", limit=POLICY_BYTES)
        except CrawlBudgetError:
            raise
        except NetworkError as error:
            probe("robots", origin + "/robots.txt", "unknown", "A protected network request failed; crawl permission could not be established.")
            warn("robots.txt could not be verified; no pages were crawled.")
            result.pages.append(Page(url=seed, outcome="blocked", error=str(error), content_type=""))
            visited.add(seed)
            await notify()
            return
        result.discovery_evidence["robots"].append((robots.url, robots.status_code))
        if robots.status_code in {404, 410}:
            result.robots_state = "absent"
            probe("robots", robots.url, "absent", "Confirmed absent at the inspected location; an empty crawl policy applies.", robots.status_code)
            policy = Protego.parse("")
        elif 200 <= robots.status_code < 300:
            media_type = robots.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            prefix = robots.body[:4096].lower()
            if (
                media_type not in {"", "text/plain", "text/x-robots"}
                or b"<html" in prefix or b"<!doctype html" in prefix
            ):
                probe("robots", robots.url, "unknown", "The response was not a usable robots.txt text policy.", robots.status_code)
                warn("robots.txt returned an unusable policy response; no pages were crawled.")
                result.pages.append(Page(url=seed, outcome="blocked", content_type="", error="robots.txt was not a usable crawl policy."))
                visited.add(seed)
                await notify()
                return
            result.robots_state = "present"
            probe("robots", robots.url, "present", "A usable robots.txt text policy was parsed; URL-specific restrictions still apply.", robots.status_code)
            policy = Protego.parse(robots.body.decode("utf-8-sig", errors="replace"))
        else:
            probe("robots", robots.url, "unknown", "The HTTP response did not establish crawl permission.", robots.status_code)
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
        result.effective_delay_seconds = delay
        await notify()
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
                if page.outcome == "html" and not targets:
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
