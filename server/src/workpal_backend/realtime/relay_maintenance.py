"""Heartbeat and bounded legacy stream maintenance for the Python relay."""
import asyncio
from dataclasses import dataclass
import logging
import time

from .relay_envelope import heartbeat_key, nodes_key, stream_key, _timestamp

log = logging.getLogger(__name__)


class _DeadlineClient:
    """Carry one operation budget across all Redis commands in a pass."""
    def __init__(self, client, stop=None):
        self.client = client
        self.stop = stop
        self.deadline = asyncio.get_running_loop().time() + 2

    def expired(self):
        return (self.stop is not None and self.stop.is_set()) or asyncio.get_running_loop().time() >= self.deadline

    def __getattr__(self, name):
        async def invoke(*args, **kwargs):
            if self.stop is not None and self.stop.is_set():
                raise RuntimeError('context canceled')
            if self.expired():
                raise TimeoutError('context deadline exceeded')
            pending = asyncio.create_task(getattr(self.client, name)(*args, **kwargs))
            stopped = asyncio.create_task(self.stop.wait()) if self.stop is not None else None
            tasks = [pending] + ([stopped] if stopped is not None else [])
            try:
                done, _ = await asyncio.wait(tasks, timeout=max(0, self.deadline - asyncio.get_running_loop().time()),
                                             return_when=asyncio.FIRST_COMPLETED)
                if pending in done:
                    return pending.result()
                if stopped in done:
                    raise RuntimeError('context canceled')
                raise TimeoutError('context deadline exceeded')
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        return invoke


@dataclass
class MaintenanceMetrics:
    connected: bool = False
    trimmed: int = 0
    retention_errors: int = 0
    streams_without_ttl: int = 0
    last_error: str = ''


class RelayMaintenance:
    def __init__(self, hub, publisher, *, clock_ns=time.time_ns, metrics=None):
        self.hub = hub
        self.client = publisher.client
        self.node_id = publisher.node_id
        self.retention = publisher.retention
        self.ttl = publisher.ttl
        self.clock_ns = clock_ns
        self.metrics = metrics if metrics is not None else MaintenanceMetrics()
        self.cursor = 0
        self.without_ttl = set()
        self._seen = set()

    async def heartbeat_once(self, stop=None):
        client = _DeadlineClient(self.client, stop)
        try:
            await client.set(heartbeat_key(self.node_id),
                             _timestamp(self.clock_ns()), ex=90)
        except Exception as error:
            self.metrics.connected = False
            self.metrics.last_error = str(error)
            return
        self.metrics.connected = True
        expiry = float((self.clock_ns() + 90_000_000_000) // 1_000_000_000)
        for scope, identity in self.hub.local_scopes():
            try:
                await client.zadd(nodes_key(scope, identity), {self.node_id: expiry})
            except Exception:
                pass

    def _error(self, error):
        self.metrics.retention_errors += 1
        self.metrics.last_error = str(error)
        log.warning('realtime/redis: stream maintenance failed: %s', error)

    async def _maintain(self, client, stream, min_id):
        try:
            self.metrics.trimmed += max(0, await client.xtrim(
                stream, minid=min_id, approximate=False))
        except Exception as error:
            self._error(error)
        ttl, error = await self.ttl.reconcile_result(client, stream, self.retention.enabled)
        if error is None or ttl in (-1, -2):
            if self.retention.enabled and ttl == -1:
                self.without_ttl.add(stream)
            else:
                self.without_ttl.discard(stream)
            self.metrics.streams_without_ttl = len(self.without_ttl)
        if error is not None:
            self._error(error)

    async def sweep_once(self, stop=None):
        now = self.clock_ns()
        min_id = f'{max(0, (now - self.retention.trim_ns) // 1_000_000)}-0'
        client = _DeadlineClient(self.client, stop)
        try:
            local = set()
            for scope, identity in self.hub.local_scopes():
                stream = stream_key(scope, identity)
                local.add(stream)
                self._seen.add(stream)
                await self._maintain(client, stream, min_id)
                try:
                    await client.zremrangebyscore(nodes_key(scope, identity), '-inf',
                                                     f'{float(now // 1_000_000_000):f}')
                except Exception:
                    pass
            next_cursor, keys = await client.scan(
                self.cursor, match='ws:scope:*:stream', count=128)
            for stream in keys:
                if isinstance(stream, bytes):
                    stream = stream.decode('utf-8', errors='surrogateescape')
                self._seen.add(stream)
                if stream not in local:
                    await self._maintain(client, stream, min_id)
            if client.expired():
                return
            self.cursor = next_cursor
            if next_cursor == 0:
                self.without_ttl.intersection_update(self._seen)
                self._seen.clear()
                self.metrics.streams_without_ttl = len(self.without_ttl)
        except Exception as error:
            self._error(error)
        finally:
            # Claims use monotonic time; never compare them to the wall clock.
            self.ttl.forget_stale(self.ttl.clock_ns() - self.retention.ttl_ns)

    async def heartbeat_loop(self, stop):
        await self._periodic(self.heartbeat_once, 30, stop)

    async def sweeper_loop(self, stop):
        await self._periodic(self.sweep_once, self.retention.maintenance_ns / 1_000_000_000, stop)

    @staticmethod
    async def _periodic(operation, period, stop):
        loop = asyncio.get_running_loop()
        next_tick = loop.time() + period
        while True:
            # An already canceled parent still runs the initial pass; its
            # commands observe cancellation and update the same error state.
            await operation(stop)
            if stop.is_set():
                return
            try:
                await asyncio.wait_for(stop.wait(), max(0, next_tick - loop.time()))
                return
            except TimeoutError:
                pass
            # Retain one pending tick and discard additional missed ticks.
            now = loop.time()
            next_tick += max(1, int((now - next_tick) // period) + 1) * period
