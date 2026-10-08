"""Per-account sending profile defaults (PRD §6.5).

Newly connected accounts start at a low cap and ramp daily (warmup, §11.10) to
protect deliverability. These mirror the DB server-defaults and are used when an
account is created.
"""

from __future__ import annotations

DEFAULT_DAILY_CAP = 200
DEFAULT_RATE_PER_MIN = 20
DEFAULT_WARMUP_DAY = 0
DEFAULT_TIMEZONE = "UTC"
DEFAULT_SEND_WINDOW = {"start": "08:00", "end": "18:00"}
