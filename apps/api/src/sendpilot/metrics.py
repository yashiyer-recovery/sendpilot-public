"""Prometheus metrics (PRD §20). Defined once; imported where instrumented."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

extraction_confidence = Histogram(
    "extraction_confidence", "Per-record extraction confidence",
    buckets=(0.0, 0.5, 0.7, 0.85, 0.9, 0.95, 0.99, 1.0),
)
extraction_latency_seconds = Histogram(
    "extraction_latency_seconds", "Extraction latency", ["path"],
)
extraction_records_total = Counter(
    "extraction_records_total", "Records extracted", ["shape"],
)
send_total = Counter("send_total", "Messages sent", ["provider", "status"])
send_latency_seconds = Histogram("send_latency_seconds", "Send latency", ["provider"])
provider_errors_total = Counter("provider_errors_total", "Provider errors", ["provider", "code"])
token_refresh_failures_total = Counter(
    "token_refresh_failures_total", "OAuth token refresh failures",
)
queue_depth = Gauge("queue_depth", "Queue depth", ["queue"])
bounces_total = Counter("bounces_total", "Bounce events", ["kind"])
complaints_total = Counter("complaints_total", "Complaint events")


def render_latest() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
