"""Explicit local-only DoH option for networks synthesizing restricted NAT64 results."""

import asyncio
import ipaddress
import json
import ssl

import httpx

from .network import NetworkError, public_address


async def resolve_google(hostname: str, port: int, *, client: httpx.AsyncClient | None = None) -> list[str]:
    """Query both A and AAAA; no fallback, redirects, DNSSEC disabling or IP exemptions."""
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return [public_address(hostname)]
    if client is None:
        async with httpx.AsyncClient(trust_env=False, verify=ssl.create_default_context(),
                                     follow_redirects=False, timeout=5) as owned:
            return await resolve_google(hostname, port, client=owned)
    try:
        addresses = []
        async with asyncio.timeout(5):
            for kind in (1, 28):
                async with client.stream("GET", "https://dns.google/resolve", params={
                    "name": hostname, "type": str(kind), "edns_client_subnet": "0.0.0.0/0", "cd": "false",
                }, headers={"Accept": "application/dns-json", "Accept-Encoding": "identity"},
                        follow_redirects=False) as response:
                    if response.status_code != 200 or response.headers.get("content-encoding", "identity") != "identity":
                        raise ValueError()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 65536:
                            raise ValueError()
                    data = json.loads(body)
                if (not isinstance(data, dict) or type(data.get("Status")) is not int or data["Status"] != 0
                        or data.get("TC") is not False or data.get("CD") is not False
                        or data.get("Question") != [{"name": hostname + ".", "type": kind}]):
                    raise ValueError()
                answers = data.get("Answer", [])
                if not isinstance(answers, list) or len(answers) > 128:
                    raise ValueError()
                for record in answers:
                    if not isinstance(record, dict):
                        raise ValueError()
                    if record.get("type") in (1, 28):
                        address = ipaddress.ip_address(record.get("data", ""))
                        if address.version != (4 if record["type"] == 1 else 6):
                            raise ValueError()
                        addresses.append(public_address(str(address)))
        if not addresses:
            raise ValueError()
        return list(dict.fromkeys(addresses))
    except NetworkError:
        raise
    except (ValueError, TypeError, KeyError, httpx.HTTPError, TimeoutError, OSError):
        raise NetworkError("The verified DNS service could not establish complete public address records.") from None
