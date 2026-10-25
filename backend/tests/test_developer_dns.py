"""Both DoH families are checked before the protected transport may connect."""

import json

import httpx
import pytest

from seopilot.developer_dns import resolve_google
from seopilot.network import NetworkError, NetworkPolicyError, NetworkResponse, fetch


def answer(kind, addresses):
    return {"Status": 0, "TC": False, "CD": False,
            "Question": [{"name": "example.org.", "type": kind}],
            "Answer": [{"name": "example.org.", "type": kind, "data": value} for value in addresses]}


@pytest.mark.asyncio
async def test_queries_both_families_and_pins_public_results():
    queries, connections = [], []

    def handle(request):
        assert str(request.url).startswith("https://dns.google/resolve?")
        assert request.url.params["edns_client_subnet"] == "0.0.0.0/0"
        kind = int(request.url.params["type"])
        queries.append(kind)
        return httpx.Response(200, json=answer(kind, ["8.8.8.8"] if kind == 1 else []))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        async def resolver(host, port):
            return await resolve_google(host, port, client=client)

        async def transport(url, address, timeout, limit):
            connections.append(address)
            return NetworkResponse(200, {"content-type": "text/html"}, b"safe")

        await fetch("https://example.org/", resolver=resolver, transport=transport)
    assert queries == [1, 28] and connections == ["8.8.8.8"]


@pytest.mark.asyncio
async def test_restricted_aaaa_blocks_otherwise_public_a():
    sent = []

    def handle(request):
        kind = int(request.url.params["type"])
        return httpx.Response(200, json=answer(kind, ["8.8.8.8"] if kind == 1 else ["64:ff9b::808:808"]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        async def resolver(host, port):
            return await resolve_google(host, port, client=client)

        async def transport(*args):
            sent.append(args)

        with pytest.raises(NetworkPolicyError):
            await fetch("https://example.org/", resolver=resolver, transport=transport)
    assert not sent


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", [
    {"Status": 2}, {"TC": True}, {"CD": True}, {"Question": []},
    {"Question": [{"name": "other.org.", "type": 1}]},
    {"Question": [{"name": "example.org.", "type": 28}]},
    {"Answer": [{"type": 1, "data": "not-an-address"}]},
    {"Answer": [{"type": 1, "data": "2001:4860:4860::8888"}]},
    {"Answer": "not-a-list"},
])
async def test_unverified_dns_responses_fail_closed(mutation):
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={**answer(1, ["8.8.8.8"]), **mutation})
    )) as client:
        with pytest.raises(NetworkError):
            await resolve_google("example.org", 443, client=client)


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    httpx.Response(302, headers={"location": "http://127.0.0.1/"}),
    httpx.Response(500, json={}), httpx.Response(200, content=b"x" * 65537),
    httpx.Response(200, content=b"invalid JSON"),
    httpx.Response(200, content=json.dumps(answer(1, [])).encode(), headers={"content-encoding": "custom"}),
])
async def test_redirects_errors_and_oversized_replies_fail_closed(response):
    requests = []

    def handle(request):
        requests.append(request)
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(NetworkError):
            await resolve_google("example.org", 443, client=client)
    assert len(requests) == 1
