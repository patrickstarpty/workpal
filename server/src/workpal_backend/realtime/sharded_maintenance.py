"""Bounded shard retention passes and missing-stream replay generations."""
import logging
import time

from .relay_maintenance import _DeadlineClient
from .sharded_config import sharded_stream_key
from .sharded_reader import stream_start_id

log = logging.getLogger(__name__)


class ShardedMaintenance:
    def __init__(self, publisher, *, clock_ns=time.time_ns):
        self.publisher = publisher
        self.config = publisher.config
        self.metrics = publisher.metrics
        self.generations = [0] * self.config.shards
        self.clock_ns = clock_ns

    def update_presence(self, shard, exists):
        if exists:
            self.publisher.seen[shard] = True
        elif self.publisher.seen[shard]:
            self.publisher.seen[shard] = False
            self.generations[shard] = (self.generations[shard] + 1) & ((1 << 64) - 1)
            self.publisher.ttl.forget(sharded_stream_key(shard))
            self.metrics.stream_missing_total += 1

    def _error(self, error):
        self.metrics.retention_errors += 1
        self.metrics.last_error = str(error)
        log.warning('realtime/sharded-redis: stream maintenance failed: %s', error)

    async def maintain_once(self, stop=None):
        client = _DeadlineClient(self.publisher.client, stop)
        minimum = stream_start_id(self.clock_ns(), self.config.trim_ns)
        without_ttl = 0
        for shard in range(self.config.shards):
            if client.expired():
                return
            key = sharded_stream_key(shard)
            try:
                exists = await client.exists(key)
            except Exception as error:
                self._error(error)
                continue
            self.update_presence(shard, bool(exists))
            if not exists:
                self.metrics.observe_stream(key, 0, -2)
                continue
            try:
                trimmed = await client.xtrim(key, minid=minimum, approximate=False)
                self.metrics.trimmed += max(0, trimmed)
            except Exception as error:
                self._error(error)
            ttl, error = await self.publisher.ttl.reconcile_result(client, key, self.config.enabled)
            if self.config.enabled and ttl == -1:
                without_ttl += 1
            if error is not None:
                self._error(error)
            try:
                length = await client.xlen(key)
            except Exception as error:
                self._error(error)
                continue
            milliseconds = ttl if ttl in (-1, -2) else (ttl // 1_000_000 if ttl >= 0 else -((-ttl) // 1_000_000))
            self.metrics.observe_stream(key, length, milliseconds)
        self.metrics.set_streams_without_ttl('sharded', without_ttl)
        await self._observe_server(client)

    async def _observe_server(self, client):
        # redis-py parses INFO into a map at its protocol boundary.
        for section, names in (('memory', (('used_memory', 'used_memory_bytes'), ('maxmemory', 'max_memory_bytes'))),
                               ('stats', (('evicted_keys', 'evicted_keys'),))):
            try:
                info = await client.info(section)
            except Exception:
                continue
            for key, attribute in names:
                value = info.get(key)
                if type(value) is int and -(1 << 63) <= value < (1 << 63):
                    setattr(self.metrics, attribute, value)
