"""SSRF protection for the crawler: only fetch public http(s) addresses.

Without this, a user could point the crawler at http://169.254.169.254 (cloud credentials),
http://localhost:5432 or an internal admin panel and read the response back through the bot.
"""

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUrl(ValueError):
    pass


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        or ip.is_multicast or ip.is_unspecified
    )


def assert_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeUrl(f"Only http(s) URLs are allowed: {url}")
    if parts.username or parts.password:
        raise UnsafeUrl("URLs with credentials are not allowed")
    host = parts.hostname
    if not host:
        raise UnsafeUrl("URL has no host")

    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise UnsafeUrl(f"Cannot resolve host {host}") from exc
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]

    # Every resolved address must be public, or a host with one public and one private record slips through.
    if not addresses or not all(_is_public(a) for a in addresses):
        raise UnsafeUrl(f"Host {host} resolves to a non-public address")
