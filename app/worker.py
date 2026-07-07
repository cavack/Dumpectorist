import asyncio
import logging
import signal

from app.core.config import settings
from app.db.session import Database
from app.runtime.job_registry import build_runtime_jobs
from app.runtime.retention import DomainRecordRetentionCleaner, RetentionPolicy
from app.runtime.scheduler import RuntimeOrchestrator
from app.runtime.supervisor import RuntimeSupervisor
from app.setups.atomic_runtime_store import AtomicReclaimRuntimeStore

logger = logging.getLogger("dumpectorist.worker")


def install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_number, stop_event.set)
        except (NotImplementedError, RuntimeError):
            logger.warning("signal_handler_unavailable signal=%s", signal_number.name)


async def run_worker() -> None:
    database = Database(settings.database_url)
    stop_event = asyncio.Event()
    install_signal_handlers(stop_event)
    jobs = build_runtime_jobs(settings)
    store = AtomicReclaimRuntimeStore(database.session_factory)
    orchestrator = RuntimeOrchestrator(jobs, store=store)
    cleaner = DomainRecordRetentionCleaner(
        database.session_factory,
        RetentionPolicy(retention_days=settings.worker_retention_days),
    )
    supervisor = RuntimeSupervisor(
        orchestrator,
        cleaner=cleaner,
        tick_seconds=settings.worker_tick_seconds,
        cleanup_interval_seconds=settings.worker_cleanup_interval_seconds,
        failure_alert_threshold=settings.worker_failure_alert_threshold,
    )
    logger.info(
        "worker_start jobs=%s retention_days=%s",
        len(jobs),
        settings.worker_retention_days,
    )
    try:
        await supervisor.run(stop_event)
    finally:
        await database.dispose()
        logger.info("worker_stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
