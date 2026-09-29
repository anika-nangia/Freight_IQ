"""Tiny in-memory TTL cache (no external infrastructure)."""
import time
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(
        self, max_entries: int = 256, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._store: dict[str, tuple[float, T]] = {}
        self._max_entries = max_entries
        self._clock = clock

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: T, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            return
        if len(self._store) >= self._max_entries:
            self._store.pop(next(iter(self._store)))
        self._store[key] = (self._clock() + ttl_seconds, value)

    def clear(self) -> None:
        self._store.clear()
