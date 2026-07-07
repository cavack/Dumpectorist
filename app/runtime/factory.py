from app.runtime.models import (
    RuntimeSchedule,
    ScheduledSourceJob,
    SourceAdapter,
    SourceJobKind,
)


def benchmark_job(
    adapter: SourceAdapter,
    *,
    interval_seconds: float,
    timeout_seconds: float,
    initial_delay_seconds: float = 0.0,
    name: str | None = None,
) -> ScheduledSourceJob:
    return _source_job(
        adapter,
        kind=SourceJobKind.BENCHMARK,
        interval_seconds=interval_seconds,
        timeout_seconds=timeout_seconds,
        initial_delay_seconds=initial_delay_seconds,
        name=name,
    )


def discovery_job(
    adapter: SourceAdapter,
    *,
    interval_seconds: float,
    timeout_seconds: float,
    initial_delay_seconds: float = 0.0,
    name: str | None = None,
) -> ScheduledSourceJob:
    return _source_job(
        adapter,
        kind=SourceJobKind.DISCOVERY,
        interval_seconds=interval_seconds,
        timeout_seconds=timeout_seconds,
        initial_delay_seconds=initial_delay_seconds,
        name=name,
    )


def _source_job(
    adapter: SourceAdapter,
    *,
    kind: SourceJobKind,
    interval_seconds: float,
    timeout_seconds: float,
    initial_delay_seconds: float,
    name: str | None,
) -> ScheduledSourceJob:
    job_name = name.strip() if name is not None else adapter.name.strip()
    if not job_name:
        raise ValueError("job name is required")
    return ScheduledSourceJob(
        name=job_name,
        kind=kind,
        adapter=adapter,
        schedule=RuntimeSchedule(
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            initial_delay_seconds=initial_delay_seconds,
        ),
    )
