"""Bounded HTTP requests that connect only to an already validated public IP."""

import asyncio
import ipaddress
import re
import socket
import ssl
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import httpcore

USER_AGENT = "SEOPilot/0.1 (bounded SEO audit)"
REDIRECT_CODES = {301, 302, 303, 307, 308}
RESTRICTED_NAMES = ("localhost", "local", "internal", "lan", "home", "invalid", "test", "onion")
RESTRICTED_IPV6 = tuple(
    ipaddress.ip_network(value)
    for value in ("64:ff9b::/96", "64:ff9b:1::/48", "2001::/23", "2002::/16", "3fff::/20")
)


class NetworkError(ValueError):
    """A deliberately sanitized, user-readable network failure."""


class NetworkPolicyError(NetworkError):
    """A URL, resolved address, or redirect is outside the permitted crawl."""


class ResponseLimitError(NetworkError):
    """The encoded or decoded response exceeded the allowed size."""


@dataclass(frozen=True)
class NetworkResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes
    url: str = ""


Resolver = Callable[[str, int], Awaitable[list[str]]]
Transport = Callable[[str, str, float, int], Awaitable[NetworkResponse]]
BeforeRequest = Callable[[str], Awaitable[None]]


def public_address(value: str) -> str:
    """Reject non-public and address-translation destinations, including mapped IPv6."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise NetworkPolicyError("The website resolved to an unsupported address.") from None
    restricted = (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
    if isinstance(address, ipaddress.IPv6Address):
        restricted = restricted or bool(
            address.scope_id
            or address.ipv4_mapped
            or address.sixtofour
            or address.teredo
            or address.is_site_local
            or any(address in network for network in RESTRICTED_IPV6)
        )
    if restricted or str(address) == "168.63.129.16":
        raise NetworkPolicyError("Only public website addresses can be audited.")
    return str(address)


def normalize_url(raw: str) -> str:
    """Canonicalize an HTTP URL without resolving it or changing query semantics."""
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 2048:
        raise ValueError("Enter an HTTP or HTTPS website URL of at most 2,048 characters.")
    if any(ord(character) < 32 or ord(character) == 127 for character in raw) or "\\" in raw:
        raise ValueError("The website URL contains unsupported characters.")
    try:
        parts = urlsplit(raw.strip())
        scheme = parts.scheme.lower()
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        raise ValueError("Enter a valid HTTP or HTTPS website URL.") from None
    if scheme not in {"http", "https"} or not hostname:
        raise ValueError("Enter a complete URL beginning with http:// or https://.")
    if "@" in parts.netloc or parts.username is not None or parts.password is not None:
        raise ValueError("Website URLs cannot contain credentials.")
    if port is not None and port != (443 if scheme == "https" else 80):
        raise ValueError("Only the standard HTTP and HTTPS website ports are allowed.")
    if "%" in hostname:
        raise ValueError("Scoped or encoded website hostnames are not supported.")
    hostname = hostname.lower().removesuffix(".")
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        if re.fullmatch(r"[0-9.]+|0[xX][0-9a-fA-F]+", hostname):
            raise ValueError("Use a standard website hostname or public IP address.") from None
        try:
            hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError:
            raise ValueError("The website hostname is not valid.") from None
        labels = hostname.split(".")
        if (
            len(hostname) > 253
            or len(labels) < 2
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
            or any(hostname == suffix or hostname.endswith("." + suffix) for suffix in RESTRICTED_NAMES)
        ):
            raise ValueError("Use a public website hostname.") from None
    else:
        hostname = public_address(str(literal))
    authority = f"[{hostname}]" if ":" in hostname else hostname
    path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = quote(parts.query, safe="/%?:@!$&'()*+,;=-._~")
    normalized = urlunsplit((scheme, authority, path, query, ""))
    if len(normalized) > 2048:
        raise ValueError("The normalized website URL is too long.")
    return normalized


def origin_of(url: str) -> str:
    parts = urlsplit(normalize_url(url))
    return f"{parts.scheme}://{parts.netloc}"


async def resolve_addresses(hostname: str, port: int) -> list[str]:
    records = await asyncio.get_running_loop().getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(record[4][0] for record in records))


class PinnedBackend(httpcore.AsyncNetworkBackend):
    """Change the TCP target while HTTPcore retains the logical Host and TLS name."""

    def __init__(self, hostname: str, port: int, address: str, delegate=None):
        self.hostname = hostname
        self.port = port
        self.address = public_address(address)
        self.delegate = delegate if delegate is not None else httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host != self.hostname or port != self.port or local_address is not None:
            raise NetworkPolicyError("The connection destination changed unexpectedly.")
        return await self.delegate.connect_tcp(
            self.address,
            self.port,
            timeout=timeout,
            local_address=None,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise NetworkPolicyError("Only public website connections are supported.")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


class BodyDecoder:
    """Limit compressed input and decoded output without an unbounded zlib flush."""

    def __init__(self, encoding: str, limit: int):
        self.limit = limit
        self.received = 0
        self.decoded = bytearray()
        encoding = encoding.strip().lower()
        if encoding in {"", "identity"}:
            self.decoder = None
        elif encoding in {"gzip", "x-gzip"}:
            self.decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        elif encoding == "deflate":
            self.decoder = zlib.decompressobj(zlib.MAX_WBITS)
        else:
            raise NetworkError("The website returned an unsupported response encoding.")

    def feed(self, chunk: bytes) -> None:
        self.received += len(chunk)
        if self.received > self.limit:
            raise ResponseLimitError("The website response exceeded the allowed size.")
        try:
            decoded = (
                self.decoder.decompress(chunk, self.limit - len(self.decoded) + 1)
                if self.decoder is not None
                else chunk
            )
        except zlib.error:
            raise NetworkError("The website returned an invalid compressed response.") from None
        if len(self.decoded) + len(decoded) > self.limit:
            raise ResponseLimitError("The decoded website response exceeded the allowed size.")
        self.decoded.extend(decoded)
        if self.decoder is not None and self.decoder.unused_data:
            raise NetworkError("The website returned unsupported concatenated compressed data.")

    def finish(self) -> bytes:
        if self.decoder is not None and not self.decoder.eof:
            raise NetworkError("The website returned an incomplete compressed response.")
        return bytes(self.decoded)


async def fetch_pinned(url: str, address: str, timeout: float, max_bytes: int) -> NetworkResponse:
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    backend = PinnedBackend(parts.hostname, port, address)
    async with httpcore.AsyncConnectionPool(
        network_backend=backend,
        ssl_context=ssl.create_default_context(),
        max_connections=1,
        max_keepalive_connections=0,
        retries=0,
        http2=False,
    ) as pool:
        async with pool.stream(
            "GET",
            url,
            headers={
                "Host": parts.netloc,
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,text/plain,application/xml,text/xml;q=0.9,*/*;q=0.1",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
            extensions={"timeout": {"connect": min(timeout, 3), "read": timeout, "write": timeout, "pool": timeout}},
        ) as response:
            headers: dict[str, str] = {}
            for name, value in response.headers:
                key = name.decode("ascii").lower()
                decoded = value.decode("latin-1")
                headers[key] = f"{headers[key]}, {decoded}" if key in headers else decoded
            media_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            binary_media = media_type.startswith(("image/", "audio/", "video/", "font/")) or media_type in {
                "application/pdf", "application/zip", "application/x-zip-compressed",
                "application/gzip", "application/x-gzip", "application/x-7z-compressed",
                "application/x-rar-compressed", "application/vnd.rar",
            }
            # Inspect metadata only for known binary resources; never download their bodies.
            if response.status in REDIRECT_CODES or binary_media:
                return NetworkResponse(response.status, headers, b"", url)
            content_length = headers.get("content-length", "")
            if content_length.isdecimal() and int(content_length) > max_bytes:
                raise ResponseLimitError("The website response exceeded the allowed size.")
            decoder = BodyDecoder(headers.get("content-encoding", ""), max_bytes)
            async for chunk in response.aiter_stream():
                decoder.feed(chunk)
            return NetworkResponse(response.status, headers, decoder.finish(), url)


async def fetch(
    url: str,
    *,
    timeout: float = 10,
    max_bytes: int = 2097152,
    allowed_origin: str | None = None,
    resolver: Resolver | None = None,
    transport: Transport | None = None,
    before_request: BeforeRequest | None = None,
    permit_url: Callable[[str], bool] | None = None,
    max_redirects: int = 5,
) -> NetworkResponse:
    """Fetch with manual same-origin redirects and fresh DNS validation at every hop."""
    try:
        current = normalize_url(url)
        permitted_origin = origin_of(allowed_origin or current)
    except ValueError as error:
        raise NetworkPolicyError(str(error)) from None
    visited: set[str] = set()
    resolve = resolver if resolver is not None else resolve_addresses
    send = transport if transport is not None else fetch_pinned
    for hop in range(max_redirects + 1):
        if origin_of(current) != permitted_origin:
            raise NetworkPolicyError("A redirect left the permitted website origin.")
        if current in visited:
            raise NetworkError("The website returned a redirect loop.")
        if permit_url is not None and not permit_url(current):
            raise NetworkPolicyError("robots.txt does not permit crawling this URL.")
        visited.add(current)
        if before_request is not None:
            await before_request(current)
        try:
            async with asyncio.timeout(timeout):
                parts = urlsplit(current)
                port = 443 if parts.scheme == "https" else 80
                addresses = await resolve(parts.hostname, port)
                if not addresses:
                    raise NetworkError("The website did not resolve to a public address.")
                validated = [public_address(address) for address in addresses]
                # Some local networks cannot reach IPv6, or one CDN address may be
                # down. Retry only already-validated IPs under this same deadline.
                for index, address in enumerate(validated[:3]):
                    if index and before_request is not None:
                        await before_request(current)
                    try:
                        response = await send(current, address, timeout, max_bytes)
                        break
                    except (httpcore.NetworkError, httpcore.TimeoutException, OSError, ssl.SSLError):
                        if index == min(3, len(validated)) - 1:
                            raise
                if len(response.body) > max_bytes:
                    raise ResponseLimitError("The website response exceeded the allowed size.")
        except TimeoutError:
            raise NetworkError("The website request timed out.") from None
        except NetworkError:
            raise
        except socket.gaierror:
            raise NetworkError("The website hostname could not be resolved.") from None
        except (httpcore.NetworkError, httpcore.ProtocolError, httpcore.TimeoutException, OSError, ssl.SSLError):
            raise NetworkError("The website could not be fetched securely.") from None
        if response.status_code not in REDIRECT_CODES:
            return NetworkResponse(response.status_code, response.headers, response.body, current)
        location = response.headers.get("location", "")
        if not location:
            raise NetworkError("The website returned a redirect without a destination.")
        if hop == max_redirects:
            raise NetworkError("The website exceeded the redirect limit.")
        try:
            current = normalize_url(urljoin(current, location))
        except ValueError as error:
            raise NetworkPolicyError(str(error)) from None
    raise NetworkError("The website exceeded the redirect limit.")

