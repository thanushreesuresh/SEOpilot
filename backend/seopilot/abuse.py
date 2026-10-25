"""Client identity comes from a socket or our authenticated local proxy."""

import hmac
import ipaddress

from fastapi import HTTPException, Request


def canonical_identity(raw: str) -> str:
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        # Missing/unknown peers share one conservative bucket, never a random ID.
        return "unknown"
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        # Rotating addresses within the same IPv6 subnet cannot reset the quota.
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def client_identity(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    token = request.headers.get("x-seopilot-proxy-token")
    forwarded = request.headers.get("x-seopilot-client-ip")
    if token is not None or forwarded is not None:
        if any(len(request.headers.getlist(name)) != 1 for name in ("x-seopilot-proxy-token", "x-seopilot-client-ip")):
            raise HTTPException(403, "Invalid local proxy credentials.")
        try:
            loopback = ipaddress.ip_address(peer).is_loopback
        except ValueError:
            loopback = False
        valid_token = token is not None and len(token) == 64 and all(char in "0123456789abcdef" for char in token)
        if not loopback or not valid_token or not forwarded or not hmac.compare_digest(token, request.app.state.proxy_token):
            raise HTTPException(403, "Invalid local proxy credentials.")
        if canonical_identity(forwarded) == "unknown":
            raise HTTPException(403, "Invalid proxy client address.")
        return canonical_identity(forwarded)
    # X-Forwarded-For, Forwarded and X-Real-IP are deliberately ignored.
    return canonical_identity(peer)


def is_loopback_client(request: Request) -> bool:
    """Inspect the original address after client_identity authenticates proxy headers."""
    raw = request.headers.get("x-seopilot-client-ip") or (request.client.host if request.client else "unknown")
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_loopback
