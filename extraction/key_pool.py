"""Groq API key rotation pool for rate-limit avoidance.

Supports multiple Groq API keys via ``GROQ_API_KEYS`` (comma-separated)
with the legacy ``GROQ_API_KEY`` as a fallback.  Keys are rotated
round-robin; on 429 responses, the next key is tried immediately instead
of waiting out the backoff.

Thread-safe: the pool is a process-level singleton protected by a lock.
"""

from __future__ import annotations

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

# Minimum delay between requests, even with multiple keys.
DEFAULT_MIN_DELAY_SECONDS = 0.5


class KeyPool:
    """Round-robin pool of API keys with inter-request rate limiting."""

    def __init__(self, min_delay: float = DEFAULT_MIN_DELAY_SECONDS) -> None:
        self._lock = threading.Lock()
        self._keys: list[str] = []
        self._index: int = 0
        self._last_used: dict[str, float] = {}
        self._min_delay = min_delay
        self._load_keys()

    def _load_keys(self) -> None:
        """Parse GROQ_API_KEYS and/or GROQ_API_KEY into the key list."""
        keys: list[str] = []

        # Multi-key env var (comma-separated)
        multi = os.environ.get("GROQ_API_KEYS", "")
        if multi:
            keys = [k.strip() for k in multi.split(",") if k.strip()]

        # Fallback to single key
        if not keys:
            single = os.environ.get("GROQ_API_KEY", "")
            if single:
                keys = [single]

        self._keys = keys

    @property
    def is_configured(self) -> bool:
        return len(self._keys) > 0

    @property
    def count(self) -> int:
        return len(self._keys)

    def next(self) -> str:
        """Return the next API key in round-robin order.

        Applies a minimum delay since the last request to avoid burning
        through all keys in a fast burst.
        """
        if not self._keys:
            raise RuntimeError(
                "No Groq API keys configured. Set GROQ_API_KEYS (comma-separated) "
                "or GROQ_API_KEY in your environment."
            )
        with self._lock:
            now = time.time()
            key = self._keys[self._index % len(self._keys)]

            # Enforce minimum delay between requests
            last = self._last_used.get(key, 0)
            elapsed = now - last
            if elapsed < self._min_delay and last > 0:
                wait = self._min_delay - elapsed
                time.sleep(wait)
                now = time.time()

            self._last_used[key] = now
            idx = self._index
            self._index = (self._index + 1) % len(self._keys)

            logger.info(
                "Key rotation: using key %d/%d (index %d)",
                idx + 1,
                len(self._keys),
                idx,
            )
            return key

    def get_key_at(self, index: int) -> str:
        """Return a specific key by index (for 429 retry with next key)."""
        if not self._keys:
            raise RuntimeError("No Groq API keys configured.")
        with self._lock:
            return self._keys[index % len(self._keys)]


# Process-level singleton
_pool: KeyPool | None = None


def get_key_pool() -> KeyPool:
    """Return the global key pool (created once per process)."""
    global _pool
    if _pool is None:
        _pool = KeyPool()
    return _pool
