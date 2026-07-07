import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.runtime.job_registry import build_runtime_jobs
from app.runtime.models import SourceJobKind


def test_registry_builds_execution_benchmark_and_discovery_jobs():
    settings = Settings(
        _env_file=None,
        worker_execution_interval_seconds=5,
        worker_benchmark_interval_seconds=10,
        worker_discovery_interval_seconds=300,
        worker_source_timeout_seconds=8,
    )

    jobs = build_runtime_jobs(settings)

    assert len(jobs) == 7
    assert [job.kind for job in jobs] == [
        SourceJobKind.EXECUTION,
        SourceJobKind.BENCHMARK,
        SourceJobKind.BENCHMARK,
        SourceJobKind.BENCHMARK,
        SourceJobKind.BENCHMARK,
        SourceJobKind.DISCOVERY,
        SourceJobKind.DISCOVERY,
    ]
    assert jobs[0].name == "lbank-execution"
    assert jobs[0].adapter.symbol == "BTCUSDT"
    assert jobs[0].schedule.interval_seconds == 5
    assert jobs[1].adapter.symbol == "BTCUSDT"
    assert jobs[3].adapter.symbol == "BTC_USDT"
    assert jobs[4].adapter.symbol == "BTC_USDT"
    assert jobs[5].schedule.initial_delay_seconds == 10
    assert jobs[6].schedule.initial_delay_seconds == 20
    assert all(job.schedule.timeout_seconds == 8 for job in jobs)


def test_registry_respects_disabled_source_groups():
    settings = Settings(
        _env_file=None,
        worker_enable_lbank=False,
        worker_enable_benchmarks=False,
        worker_enable_discovery=True,
    )

    jobs = build_runtime_jobs(settings)

    assert len(jobs) == 2
    assert all(job.kind == SourceJobKind.DISCOVERY for job in jobs)


def test_settings_reject_blank_symbols_and_empty_registry():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, worker_binance_symbol=" ")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            worker_enable_lbank=False,
            worker_enable_benchmarks=False,
            worker_enable_discovery=False,
        )


def test_settings_validate_worker_intervals():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, worker_tick_seconds=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, worker_retention_days=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, worker_failure_alert_threshold=0)
