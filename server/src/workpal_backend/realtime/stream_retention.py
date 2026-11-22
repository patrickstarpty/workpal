"""Shared relay retention and rate-limited TTL repair.

Durations use integer nanoseconds, including Go Redis's -1/-2 sentinel values.
Redis-py exposes PTTL in milliseconds, converted only at the client boundary.
"""
from dataclasses import dataclass, replace
from threading import Lock
import time

SECOND = 1_000_000_000


def _subinterval(ttl, preferred):
    return preferred if 0 < preferred < ttl else max(1, ttl // 3)


@dataclass(frozen=True)
class RetentionConfig:
    max_len: int = 0
    trim_ns: int = 0
    ttl_ns: int = 0
    refresh_ns: int = 0
    maintenance_ns: int = 0
    enabled: bool = False

    def with_defaults(self):
        trim = self.trim_ns if self.trim_ns > 0 else 600 * SECOND
        ttl = self.ttl_ns
        if ttl < trim:
            # Go time.Duration addition wraps at signed int64 boundaries.
            ttl = (trim + 300 * SECOND + (1 << 63)) % (1 << 64) - (1 << 63)
        return replace(self, max_len=self.max_len if self.max_len > 0 else 2000,
                       trim_ns=trim, ttl_ns=ttl,
                       refresh_ns=self.refresh_ns if 0 < self.refresh_ns < ttl else _subinterval(ttl, 30 * SECOND),
                       maintenance_ns=self.maintenance_ns if 0 < self.maintenance_ns < ttl else _subinterval(ttl, 60 * SECOND))


class TTLRefresher:
    def __init__(self, ttl_ns, refresh_ns, *, clock_ns=time.monotonic_ns):
        self.ttl_ns = ttl_ns
        self.refresh_ns = refresh_ns
        self.clock_ns = clock_ns
        self._lock = Lock()
        self._last = {}

    def claim(self, key, now):
        with self._lock:
            if key in self._last and now - self._last[key] < self.refresh_ns:
                return False
            self._last[key] = now
            return True

    def release(self, key, claimed_at):
        with self._lock:
            if self._last.get(key) == claimed_at:
                self._last.pop(key, None)

    def forget(self, key):
        with self._lock:
            self._last.pop(key, None)

    def forget_stale(self, before):
        with self._lock:
            self._last = {key: at for key, at in self._last.items() if at >= before}

    def _expiry_ms(self):
        # go-redis rounds positive sub-millisecond expirations up to 1ms.
        return max(1, self.ttl_ns // 1_000_000) if self.ttl_ns > 0 else -((-self.ttl_ns) // 1_000_000)

    async def refresh_if_due(self, client, key):
        now = self.clock_ns()
        if not self.claim(key, now):
            return
        try:
            if not await client.pexpire(key, self._expiry_ms()):
                raise RuntimeError(f'stream {key!r} disappeared before TTL refresh')
        except BaseException:
            self.release(key, now)
            raise

    async def reconcile(self, client, key, enabled):
        ttl, error = await self.reconcile_result(client, key, enabled)
        if error is not None:
            raise error
        return ttl

    async def reconcile_result(self, client, key, enabled):
        # Go returns the observed TTL alongside a repair error. Maintenance
        # needs that observation to count streams whose expiry repair failed.
        ttl = 0
        try:
            ttl_ms = await client.pttl(key)
            ttl = ttl_ms if ttl_ms in (-2, -1) else ttl_ms * 1_000_000
            if not enabled:
                self.forget(key)
                if ttl in (-2, -1):
                    return ttl, None
                return (-1 if await client.persist(key) else -2), None
            if ttl != -1:
                return ttl, None
            if not await client.pexpire(key, self._expiry_ms()):
                return -2, None
            with self._lock:
                self._last[key] = self.clock_ns()
            return self.ttl_ns, None
        except Exception as error:
            return ttl, error
