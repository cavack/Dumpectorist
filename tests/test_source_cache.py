import pytest

from app.adapters.source_cache import (
    AsyncTtlCache,
    RequestBudgetExceeded,
    SlidingWindowBudget,
)


@pytest.mark.asyncio
async def test_ttl_cache_expires_entries():
    now = [100.0]
    cache: AsyncTtlCache[str] = AsyncTtlCache(10.0, clock=lambda: now[0])

    await cache.set("key", "value")
    assert await cache.get("key") == "value"

    now[0] = 110.0
    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_cache_clear_removes_entries():
    cache: AsyncTtlCache[int] = AsyncTtlCache(10.0)
    await cache.set("one", 1)

    await cache.clear()

    assert await cache.get("one") is None


@pytest.mark.asyncio
async def test_sliding_window_budget_blocks_and_recovers():
    now = [100.0]
    budget = SlidingWindowBudget(
        max_requests=2,
        window_seconds=60.0,
        clock=lambda: now[0],
    )

    await budget.acquire()
    await budget.acquire()
    with pytest.raises(RequestBudgetExceeded):
        await budget.acquire()

    now[0] = 160.0
    await budget.acquire()


def test_source_controls_reject_invalid_configuration():
    with pytest.raises(ValueError):
        AsyncTtlCache(0)
    with pytest.raises(ValueError):
        SlidingWindowBudget(0, 60)
    with pytest.raises(ValueError):
        SlidingWindowBudget(1, 0)
