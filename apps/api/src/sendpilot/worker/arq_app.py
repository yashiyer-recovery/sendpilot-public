"""Arq worker entrypoint: ``arq sendpilot.worker.arq_app.WorkerSettings``."""

from __future__ import annotations

from arq import cron

from ..extraction.orchestrator import run_extraction
from ..ingestion.antivirus import av_scan
from ..ingestion.storage import ensure_bucket
from ..logging import configure_logging, get_logger
from ..privacy.purge import purge_expired_documents
from ..queue import redis_settings
from ..sending.worker import send_message_task

log = get_logger("worker")


async def startup(ctx: dict) -> None:
    configure_logging()
    await ensure_bucket()
    log.info("worker.started")


async def shutdown(ctx: dict) -> None:
    log.info("worker.stopped")


class WorkerSettings:
    functions = [av_scan, run_extraction, send_message_task]
    cron_jobs = [cron(purge_expired_documents, hour=3, minute=0)]  # daily retention purge
    redis_settings = redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 20
