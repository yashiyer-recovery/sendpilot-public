"""MX lookup with a simple in-process cache (PRD §9). Optional/off locally."""

from __future__ import annotations

_mx_cache: dict[str, bool] = {}


def has_mx(domain: str) -> bool:
    if domain in _mx_cache:
        return _mx_cache[domain]
    try:
        import dns.resolver

        ok = len(dns.resolver.resolve(domain, "MX")) > 0
    except Exception:
        ok = False
    _mx_cache[domain] = ok
    return ok
