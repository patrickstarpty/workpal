"""Fixed-shard publishing with shared expiry state and stream presence."""
import asyncio
import logging
import time

from .relay_envelope import new_envelope, redis_values
from .relay_metrics import RedisMetrics
from .sharded_config import ShardedConfig, shard_for, sharded_stream_key
from .stream_retention import TTLRefresher

log = logging.getLogger(__name__)


class ShardedPublisher:
    def __init__(self, client, node_id, *, config=None, metrics=None, seen=None,
                 clock_ns=time.time_ns):
        self.client = client
        self.node_id = node_id
        self.config = (config or ShardedConfig()).with_defaults()
        self.metrics = metrics if metrics is not None else RedisMetrics()
        self.seen = seen if seen is not None else [False] * self.config.shards
        self.clock_ns = clock_ns
        self.ttl = TTLRefresher(self.config.ttl_ns, self.config.refresh_ns)

    async def publish_with_id(self, scope, identity, exclude, frame, event_id):
        envelope = new_envelope(self.node_id, scope, identity, exclude, frame,
                                event_id, clock_ns=self.clock_ns)
        shard = shard_for(scope, identity, self.config.shards)
        key = sharded_stream_key(shard)
        start = time.monotonic_ns()
        try:
            await asyncio.wait_for(self.client.xadd(
                key, redis_values(envelope), maxlen=self.config.max_len,
                approximate=True), 2)
        except Exception as error:
            self.metrics.xadd_errors += 1
            self.metrics.last_error = str(error)
            log.warning('realtime/sharded-redis: XADD failed: %s', error)
            raise
        self.metrics.xadd_total += 1
        elapsed = time.monotonic_ns() - start
        self.metrics.last_xadd_lag_micros = elapsed // 1000
        self.seen[shard] = True
        if self.config.enabled:
            try:
                await asyncio.wait_for(self.ttl.refresh_if_due(self.client, key),
                                       max(0, 2 - elapsed / 1_000_000_000))
            except Exception as error:
                self.metrics.retention_errors += 1
                self.metrics.last_error = str(error)
                log.warning('realtime/sharded-redis: PEXPIRE failed: %s', error)
