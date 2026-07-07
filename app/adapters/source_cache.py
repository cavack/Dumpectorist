from asyncio import Lock
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Generic, TypeVar


T = TypeVar("T")


class RequestBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class AsyncTtlCache(Generic[T]):
    def __init__(
        self,
        ttl_seconds: float,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._items: dict[str, CacheEntry[T]] = {}
        self._lock = Lock()

    async def get(self, key: str) -> T | None:
        async with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if entry.expires_at <= self.clock():
                self._items.pop(key, None)
                return None
            return entry.value

    async def set(self, key: str, value: T) -> None:
        async with self._lock:
            self._items[key] = CacheEntry(
                value=value,
                expires_at=self.clock() + self.ttl_seconds,
            )

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()


class SlidingWindowBudget:
    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clock = clock
        self._requests: deque[float] = deque()
        self._lock = Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = self.clock()
            boundary = now - self.window_seconds
            while self._requests and self._requests[0] <= boundary:
                self._requests.popleft()
            if len(self._requests) >= self.max_requests:
                raise RequestBudgetExceeded("source request budget exceeded")
            self._requests.append(now)
