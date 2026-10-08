"""Shared test configuration."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _quiet_logging():
    from sendpilot.logging import configure_logging

    configure_logging()
