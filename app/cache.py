"""Lightweight in-memory content-hash cache for tool results.

Evicts least-recently-used entries when the cache exceeds *max_size*.
Thread-safe via an ``OrderedDict`` with a simple lock.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any

_DEFAULT_MAX_SIZE = 256


class ContentCache:
    def __init__(self, max_size: int = _DEFAULT_MAX_SIZE) -> None:
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(*parts: str) -> str:
        raw = "\0".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, cache_key: str) -> Any | None:
        with self._lock:
            if cache_key in self._store:
                self._store.move_to_end(cache_key)
                self.hits += 1
                return self._store[cache_key]
            self.misses += 1
            return None

    def put(self, cache_key: str, value: Any) -> None:
        with self._lock:
            if cache_key in self._store:
                self._store.move_to_end(cache_key)
            self._store[cache_key] = value
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0

    @property
    def stats(self) -> dict:
        return {"size": len(self._store), "max_size": self._max_size, "hits": self.hits, "misses": self.misses}


# Singleton used across tools
tool_cache = ContentCache()
