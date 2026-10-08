"""Warmup ramp for new mailboxes (PRD §11.10)."""

from __future__ import annotations

# Gradual daily-volume ramp on a brand-new account, to protect deliverability.
SCHEDULE = [20, 40, 80, 120, 160, 200, 300, 400]


def effective_daily_cap(warmup_day: int, configured_cap: int) -> int:
    if warmup_day >= len(SCHEDULE):
        return configured_cap
    return min(configured_cap, SCHEDULE[warmup_day])
