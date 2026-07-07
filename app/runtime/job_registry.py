from app.adapters.binance_futures import BinanceUsdMAdapter
from app.adapters.bybit_futures import BybitLinearPerpetualAdapter
from app.adapters.bybit_kline import BybitKlineAdapter
from app.adapters.coingecko import CoinGeckoDiscoveryAdapter, CoinGeckoFeed
from app.adapters.dex_screener import DexScreenerAdapter, DexScreenerFeed
from app.adapters.gate_public import GateUsdtFuturesAdapter
from app.adapters.lbank import LBankPublicAdapter
from app.adapters.mexc_futures import MexcUsdtPerpetualAdapter
from app.candles.models import CandleInterval
from app.core.config import Settings
from app.runtime.factory import benchmark_job, discovery_job, execution_job, structure_job
from app.runtime.models import ScheduledSourceJob


def build_runtime_jobs(settings: Settings) -> tuple[ScheduledSourceJob, ...]:
    jobs: list[ScheduledSourceJob] = []
    timeout = settings.worker_source_timeout_seconds

    if settings.worker_enable_lbank:
        jobs.append(
            execution_job(
                LBankPublicAdapter(symbol=settings.worker_lbank_symbol),
                interval_seconds=settings.worker_execution_interval_seconds,
                timeout_seconds=timeout,
                initial_delay_seconds=0,
                name="lbank-execution",
            )
        )

    if settings.worker_enable_benchmarks:
        interval = settings.worker_benchmark_interval_seconds
        jobs.extend(
            (
                benchmark_job(
                    BinanceUsdMAdapter(symbol=settings.worker_binance_symbol),
                    interval_seconds=interval,
                    timeout_seconds=timeout,
                    initial_delay_seconds=1,
                    name="binance-usdm-benchmark",
                ),
                benchmark_job(
                    BybitLinearPerpetualAdapter(symbol=settings.worker_bybit_symbol),
                    interval_seconds=interval,
                    timeout_seconds=timeout,
                    initial_delay_seconds=2,
                    name="bybit-linear-benchmark",
                ),
                benchmark_job(
                    MexcUsdtPerpetualAdapter(symbol=settings.worker_mexc_symbol),
                    interval_seconds=interval,
                    timeout_seconds=timeout,
                    initial_delay_seconds=3,
                    name="mexc-usdt-benchmark",
                ),
                benchmark_job(
                    GateUsdtFuturesAdapter(symbol=settings.worker_gate_symbol),
                    interval_seconds=interval,
                    timeout_seconds=timeout,
                    initial_delay_seconds=4,
                    name="gate-usdt-benchmark",
                ),
            )
        )

    if settings.worker_enable_ohlcv:
        interval = settings.worker_ohlcv_interval_seconds
        jobs.extend(
            (
                structure_job(
                    BybitKlineAdapter(
                        symbol=settings.worker_ohlcv_symbol,
                        interval=CandleInterval.D1,
                        limit=settings.worker_ohlcv_limit,
                    ),
                    interval_seconds=interval,
                    timeout_seconds=timeout,
                    initial_delay_seconds=5,
                    name="bybit-ohlcv-1d",
                ),
                structure_job(
                    BybitKlineAdapter(
                        symbol=settings.worker_ohlcv_symbol,
                        interval=CandleInterval.H4,
                        limit=settings.worker_ohlcv_limit,
                    ),
                    interval_seconds=interval,
                    timeout_seconds=timeout,
                    initial_delay_seconds=6,
                    name="bybit-ohlcv-4h",
                ),
                structure_job(
                    BybitKlineAdapter(
                        symbol=settings.worker_ohlcv_symbol,
                        interval=CandleInterval.M15,
                        limit=settings.worker_ohlcv_limit,
                    ),
                    interval_seconds=interval,
                    timeout_seconds=timeout,
                    initial_delay_seconds=7,
                    name="bybit-ohlcv-15m",
                ),
            )
        )

    if settings.worker_enable_discovery:
        interval = settings.worker_discovery_interval_seconds
        jobs.extend(
            (
                discovery_job(
                    DexScreenerAdapter(feed=DexScreenerFeed.BOOSTS),
                    interval_seconds=interval,
                    timeout_seconds=timeout,
                    initial_delay_seconds=10,
                    name="dex-screener-boosts",
                ),
                discovery_job(
                    CoinGeckoDiscoveryAdapter(feed=CoinGeckoFeed.CATEGORIES),
                    interval_seconds=interval,
                    timeout_seconds=timeout,
                    initial_delay_seconds=20,
                    name="coingecko-categories",
                ),
            )
        )

    if not jobs:
        raise ValueError("runtime registry produced no jobs")
    return tuple(jobs)
