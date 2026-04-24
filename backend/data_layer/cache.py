"""
NPIDE - Cache layer.

Uses Redis when available, but can fall back to an in-process memory store so
the project remains runnable on machines without Redis installed.
"""

from __future__ import annotations

import fnmatch
import json
import os
import time
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

CHANNELS = {
    "grievance_filed": "npide:events:grievance",
    "scheme_updated": "npide:events:scheme",
    "cache_bust": "npide:events:cache_bust",
    "spike_alert": "npide:events:spike",
}

_CACHE_BACKEND = os.getenv("CACHE_BACKEND", "memory").lower()


class _MemoryStore:
    def __init__(self):
        self._values: dict[str, tuple[str, float | None]] = {}

    def _purge(self) -> None:
        now = time.time()
        expired = [key for key, (_value, expires_at) in self._values.items() if expires_at is not None and expires_at <= now]
        for key in expired:
            self._values.pop(key, None)

    def get(self, key: str) -> Optional[str]:
        self._purge()
        item = self._values.get(key)
        return item[0] if item else None

    def setex(self, key: str, ttl: int, value: str) -> bool:
        self._values[key] = (value, time.time() + ttl if ttl else None)
        return True

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self._values:
                removed += 1
                self._values.pop(key, None)
        return removed

    def incr(self, key: str) -> int:
        current = int(self.get(key) or 0) + 1
        self._values[key] = (str(current), self._values.get(key, (None, None))[1])
        return current

    def expire(self, key: str, ttl: int) -> bool:
        value = self.get(key)
        if value is None:
            return False
        self._values[key] = (value, time.time() + ttl if ttl else None)
        return True

    def scan_iter(self, pattern: str):
        self._purge()
        for key in list(self._values.keys()):
            if fnmatch.fnmatch(key, pattern):
                yield key

    def ping(self) -> bool:
        return True

    def publish(self, _channel: str, _payload: str) -> int:
        return 0

    def pubsub(self):
        return _MemoryPubSub()


class _MemoryPubSub:
    def subscribe(self, *_channels):
        return None

    def unsubscribe(self):
        return None

    def listen(self):
        if False:
            yield None
        return


class _MemorySyncRedis:
    def __init__(self, store: _MemoryStore):
        self.store = store

    def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> bool:
        return self.store.setex(key, ttl, value)

    def delete(self, *keys: str) -> int:
        return self.store.delete(*keys)

    def incr(self, key: str) -> int:
        return self.store.incr(key)

    def expire(self, key: str, ttl: int) -> bool:
        return self.store.expire(key, ttl)

    def scan_iter(self, pattern: str):
        return self.store.scan_iter(pattern)

    def ping(self) -> bool:
        return self.store.ping()

    def publish(self, channel: str, payload: str) -> int:
        return self.store.publish(channel, payload)

    def pubsub(self):
        return self.store.pubsub()


class _MemoryAsyncRedis:
    def __init__(self, store: _MemoryStore):
        self.store = store

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        return self.store.setex(key, ttl, value)

    async def delete(self, *keys: str) -> int:
        return self.store.delete(*keys)

    async def ping(self) -> bool:
        return self.store.ping()

    async def publish(self, channel: str, payload: str) -> int:
        return self.store.publish(channel, payload)

    async def scan_iter(self, pattern: str):
        for key in self.store.scan_iter(pattern):
            yield key


_memory_store = _MemoryStore()
_redis_sync = None
_redis_async = None

if _CACHE_BACKEND == "redis":
    try:
        import redis
        import redis.asyncio as aioredis

        _HOST = os.getenv("REDIS_HOST", "localhost")
        _PORT = int(os.getenv("REDIS_PORT", 6379))
        _DB = int(os.getenv("REDIS_DB", 0))
        _KW = dict(
            host=_HOST,
            port=_PORT,
            db=_DB,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _async_pool = aioredis.ConnectionPool(**_KW, max_connections=20)
        _sync_pool = redis.ConnectionPool(**_KW, max_connections=20)
        _redis_async = aioredis.Redis(connection_pool=_async_pool)
        _redis_sync = redis.Redis(connection_pool=_sync_pool)
    except Exception:
        _CACHE_BACKEND = "memory"

if _CACHE_BACKEND == "memory":
    ASYNC_REDIS = _MemoryAsyncRedis(_memory_store)
    REDIS = _MemorySyncRedis(_memory_store)
else:
    ASYNC_REDIS = _redis_async
    REDIS = _redis_sync


async def async_cache_get(key: str) -> Optional[Any]:
    try:
        raw = await ASYNC_REDIS.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def async_cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    try:
        await ASYNC_REDIS.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception:
        return False


async def async_cache_delete(key: str) -> bool:
    try:
        await ASYNC_REDIS.delete(key)
        return True
    except Exception:
        return False


async def async_delete_by_prefix(prefix: str) -> int:
    try:
        keys = [key async for key in ASYNC_REDIS.scan_iter(f"{prefix}*")]
        if not keys:
            return 0
        return await ASYNC_REDIS.delete(*keys)
    except Exception:
        return 0


async def async_ping_redis() -> bool:
    try:
        return await ASYNC_REDIS.ping()
    except Exception:
        return False


def cache_get(key: str) -> Optional[Any]:
    try:
        raw = REDIS.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    try:
        REDIS.setex(key, ttl_seconds, json.dumps(value, default=str))
        return True
    except Exception:
        return False


def cache_delete(key: str) -> bool:
    try:
        REDIS.delete(key)
        return True
    except Exception:
        return False


def cache_incr(key: str, ttl_seconds: int = 300) -> int:
    try:
        count = REDIS.incr(key)
        REDIS.expire(key, ttl_seconds)
        return count
    except Exception:
        return 0


def cache_get_raw(key: str) -> Optional[str]:
    try:
        return REDIS.get(key)
    except Exception:
        return None


def cache_set_raw(key: str, value: str, ttl_seconds: int = 3600) -> bool:
    try:
        REDIS.setex(key, ttl_seconds, value)
        return True
    except Exception:
        return False


def ping_redis() -> bool:
    try:
        return REDIS.ping()
    except Exception:
        return False


async def publish_event(channel_key: str, payload: dict) -> None:
    try:
        channel = CHANNELS.get(channel_key, channel_key)
        await ASYNC_REDIS.publish(channel, json.dumps(payload, default=str))
    except Exception as e:
        print(f"[EVENT-BUS] {channel_key}: {e}")


def publish_event_sync(channel_key: str, payload: dict) -> None:
    try:
        channel = CHANNELS.get(channel_key, channel_key)
        REDIS.publish(channel, json.dumps(payload, default=str))
    except Exception as e:
        print(f"[EVENT-BUS-SYNC] {channel_key}: {e}")
