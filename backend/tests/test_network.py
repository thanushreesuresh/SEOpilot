import asyncio
import gzip
import ssl
import zlib

import httpcore
import pytest

from seopilot.network import (
    BodyDecoder,
    NetworkError,
    NetworkPolicyError,
    NetworkResponse,
    PinnedBackend,
    ResponseLimitError,
    fetch,
    normalize_url,
    origin_of,
    public_address,
)


@pytest.mark.parametrize("address", [
    "0.0.0.0", "10.0.0.1", "127.0.0.1", "172.16.1.1", "192.168.1.1", "169.254.169.254",
    "100.100.100.200", "100.64.0.1", "192.0.2.1", "198.18.0.1", "198.51.100.1", "203.0.113.1",
    "224.0.0.1", "240.0.0.1", "255.255.255.255", "168.63.129.16", "::", "::1", "fc00::1",
    "fe80::1", "ff02::1", "fec0::1", "::ffff:127.0.0.1", "::ffff:8.8.8.8", "2001:db8::1",
    "64:ff9b::a00:1", "2002:a00:1::", "2001::1", "3fff::1", "fe80::1%eth0",
])
def test_blocks_restricted_destinations(address):
    with pytest.raises(NetworkPolicyError):
        public_address(address)


@pytest.mark.parametrize("address", ["8.8.8.8", "93.184.215.14", "2001:4860:4860::8888"])
def test_accepts_public_unicast(address):
    assert public_address(address) == address


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com/", "https://user:secret@example.com/", "http://localhost/",
    "http://foo.local/", "http://127.0.0.1/", "http://2130706433/", "http://0x7f000001/", "http://127.1/",
    "https://[::ffff:127.0.0.1]/", "https://example.com:444/", "https://example.com:80/",
    "https://example.com\\@localhost/", "https://example.com/\nprivate", "https://[fe80::1%25eth0]/",
    "https://bad_host.example.com/", "https://example..com/", "https://example.com:" + "9" * 10,
])
def test_rejects_unsafe_url_syntax(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_url_normalization_preserves_semantics():
    assert normalize_url(" HTTPS://EXAMPLE.COM.:443/a%2Fb/?z=1&a=2#section ") == "https://example.com/a%2Fb/?z=1&a=2"
    assert normalize_url("https://example.com/café?q=hello world") == "https://example.com/caf%C3%A9?q=hello%20world"
    assert origin_of("https://example.com:443/path") == "https://example.com"


async def public_dns(hostname, port):
    return ["93.184.215.14"]


@pytest.mark.asyncio
async def test_connection_falls_back_only_to_already_validated_addresses():
    addresses = ["2001:4860:4860::8888", "93.184.215.14"]
    attempted = []
    counted = []

    async def resolver(host, port):
        return addresses

    async def transport(url, address, timeout, limit):
        attempted.append(address)
        if address == addresses[0]:
            raise httpcore.ConnectError("unreachable address")
        return NetworkResponse(200, {"content-type": "text/html"}, b"ok")

    async def before(url):
        counted.append(url)

    response = await fetch("https://example.com/", resolver=resolver, transport=transport, before_request=before)
    assert response.status_code == 200
    assert attempted == addresses and len(counted) == 2


@pytest.mark.asyncio
async def test_dns_is_checked_and_selected_address_is_passed_to_transport():
    observed = []

    async def transport(url, address, timeout, limit):
        observed.append((url, address))
        return NetworkResponse(200, {"content-type": "text/html"}, b"ok")

    response = await fetch("https://example.com/", resolver=public_dns, transport=transport)
    assert response.url == "https://example.com/"
    assert observed == [("https://example.com/", "93.184.215.14")]


@pytest.mark.asyncio
async def test_mixed_public_private_dns_answers_fail_closed():
    sent = []

    async def resolver(host, port):
        return ["93.184.215.14", "10.0.0.1"]

    async def transport(*args):
        sent.append(args)
        raise AssertionError("Private DNS answers must prevent the request")

    with pytest.raises(NetworkPolicyError):
        await fetch("https://example.com/", resolver=resolver, transport=transport)
    assert sent == []


@pytest.mark.asyncio
async def test_redirect_resolution_rechecks_dns_before_connecting():
    resolutions = iter([["93.184.215.14"], ["127.0.0.1"]])
    sent = []

    async def resolver(host, port):
        return next(resolutions)

    async def transport(url, address, timeout, limit):
        sent.append(url)
        return NetworkResponse(302, {"location": "/next"}, b"")

    with pytest.raises(NetworkPolicyError):
        await fetch("https://example.com/", resolver=resolver, transport=transport)
    assert sent == ["https://example.com/"]


@pytest.mark.asyncio
@pytest.mark.parametrize("location", ["http://127.0.0.1/", "https://other.example.com/", "http://example.com/"])
async def test_redirect_cannot_leave_origin_or_access_private_url(location):
    sent = []

    async def transport(url, address, timeout, limit):
        sent.append(url)
        return NetworkResponse(302, {"location": location}, b"")

    with pytest.raises(NetworkPolicyError):
        await fetch("https://example.com/", resolver=public_dns, transport=transport)
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_redirect_policy_and_rate_hook_apply_on_each_hop():
    sent = []
    delayed = []

    async def transport(url, address, timeout, limit):
        sent.append(url)
        return NetworkResponse(302, {"location": "/private"}, b"")

    async def before(url):
        delayed.append(url)

    with pytest.raises(NetworkPolicyError, match="robots"):
        await fetch(
            "https://example.com/", resolver=public_dns, transport=transport,
            before_request=before, permit_url=lambda url: not url.endswith("/private"),
        )
    assert sent == delayed == ["https://example.com/"]


@pytest.mark.asyncio
async def test_redirect_limit_and_loop_are_bounded():
    calls = []

    async def redirect(url, address, timeout, limit):
        calls.append(url)
        return NetworkResponse(302, {"location": f"/next/{len(calls)}"}, b"")

    with pytest.raises(NetworkError, match="redirect limit"):
        await fetch("https://example.com/", resolver=public_dns, transport=redirect, max_redirects=2)
    assert len(calls) == 3

    async def loop(*args):
        return NetworkResponse(301, {"location": "/"}, b"")

    with pytest.raises(NetworkError, match="loop"):
        await fetch("https://example.com/", resolver=public_dns, transport=loop)


@pytest.mark.asyncio
async def test_timeout_cancels_inflight_request():
    cancelled = asyncio.Event()

    async def transport(*args):
        try:
            await asyncio.sleep(1)
        finally:
            cancelled.set()

    with pytest.raises(NetworkError, match="timed out"):
        await fetch("https://example.com/", resolver=public_dns, transport=transport, timeout=0.01)
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_empty_dns_and_transport_overflow_are_safe_failures():
    async def empty_dns(*args):
        return []

    with pytest.raises(NetworkError, match="resolve"):
        await fetch("https://example.com/", resolver=empty_dns)

    async def oversized(*args):
        return NetworkResponse(200, {}, b"a" * 100)

    with pytest.raises(ResponseLimitError):
        await fetch("https://example.com/", resolver=public_dns, transport=oversized, max_bytes=50)


@pytest.mark.parametrize("encoding,body", [("gzip", gzip.compress(b"hello")), ("deflate", zlib.compress(b"hello"))])
def test_bounded_decompression_accepts_complete_streams(encoding, body):
    decoder = BodyDecoder(encoding, 100)
    for offset in range(0, len(body), 3):
        decoder.feed(body[offset:offset + 3])
    assert decoder.finish() == b"hello"


def test_compression_bomb_and_encoded_overflow_are_rejected():
    decoder = BodyDecoder("gzip", 1024)
    with pytest.raises(ResponseLimitError):
        decoder.feed(gzip.compress(b"x" * 100000))
    identity = BodyDecoder("identity", 10)
    with pytest.raises(ResponseLimitError):
        identity.feed(b"x" * 11)


def test_invalid_incomplete_and_concatenated_compression_are_rejected():
    with pytest.raises(NetworkError):
        BodyDecoder("br", 100)
    bad = BodyDecoder("gzip", 100)
    with pytest.raises(NetworkError):
        bad.feed(b"not gzip")
    incomplete = BodyDecoder("gzip", 100)
    incomplete.feed(gzip.compress(b"hello")[:-3])
    with pytest.raises(NetworkError, match="incomplete"):
        incomplete.finish()
    concatenated = BodyDecoder("gzip", 100)
    with pytest.raises(NetworkError, match="concatenated"):
        concatenated.feed(gzip.compress(b"one") + gzip.compress(b"two"))


@pytest.mark.asyncio
async def test_pinned_public_backend_preserves_original_host_sni_and_tls_verification():
    observed = {}

    class Stream(httpcore.AsyncMockStream):
        async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
            observed["sni"] = server_hostname
            observed["verify"] = ssl_context.verify_mode
            observed["check_hostname"] = ssl_context.check_hostname
            return self

        async def write(self, buffer, timeout=None):
            observed.setdefault("writes", []).append(buffer)

    class Delegate(httpcore.AsyncNetworkBackend):
        async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            observed["tcp"] = (host, port)
            return Stream([b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"])

    backend = PinnedBackend("example.com", 443, "93.184.215.14", delegate=Delegate())
    async with asyncio.timeout(2):
        async with httpcore.AsyncConnectionPool(network_backend=backend, max_keepalive_connections=0) as pool:
            response = await pool.request("GET", "https://example.com/", headers={"Host": "example.com"})
    assert response.content == b"OK"
    assert observed["tcp"] == ("93.184.215.14", 443)
    assert observed["sni"] == "example.com"
    assert observed["verify"] == ssl.CERT_REQUIRED
    assert observed["check_hostname"] is True
    assert b"Host: example.com" in b"".join(observed["writes"])
    with pytest.raises(NetworkPolicyError):
        await backend.connect_tcp("other.example.com", 443)


@pytest.mark.asyncio
@pytest.mark.parametrize("media_type,should_read", [
    ("application/pdf", False), ("image/png", False), ("application/zip", False),
    ("video/mp4", False), ("audio/mpeg", False), ("font/woff2", False),
    ("text/plain; charset=utf-8", True), ("text/x-robots", True),
    ("application/xml", True), ("text/xml", True), ("text/html", True),
    ("application/octet-stream", True), ("", True),
])
async def test_live_transport_closes_known_binary_body_but_keeps_policy_and_xml_streams(
    monkeypatch, media_type, should_read,
):
    from contextlib import asynccontextmanager

    from seopilot import network

    reads = []

    class Response:
        status = 200
        headers = [(b"content-type", media_type.encode()), (b"x-fixture", b"preserved")]

        async def aiter_stream(self):
            reads.append(True)
            yield b"payload"

    class Pool:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            yield Response()

    monkeypatch.setattr(network.httpcore, "AsyncConnectionPool", lambda **kwargs: Pool())
    response = await network.fetch_pinned("https://example.com/resource", "93.184.215.14", 10, 1024)
    assert bool(reads) is should_read
    assert response.body == (b"payload" if should_read else b"")
    assert response.status_code == 200
    assert response.headers["content-type"] == media_type
    assert response.headers["x-fixture"] == "preserved"
