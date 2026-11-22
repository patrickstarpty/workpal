"""Per-scope Redis stream publishing, shared by relay delivery modes."""
import asyncio
from dataclasses import dataclass
import logging
import time

from .relay_envelope import new_envelope, redis_values, stream_key
from .stream_retention import RetentionConfig, TTLRefresher

log = logging.getLogger(__name__)


@dataclass
class PublishMetrics:
    xadd_total: int = 0
    xadd_errors: int = 0
    last_xadd_lag_micros: int = 0
    retention_errors: int = 0
    last_error: str = ''


class RelayPublisher:
    def __init__(self, client, node_id, *, retention=None, metrics=None,
                 clock_ns=time.time_ns):
        self.client = client
        self.node_id = node_id
        self.retention = (retention or RetentionConfig()).with_defaults()
        self.metrics = metrics if metrics is not None else PublishMetrics()
        self.clock_ns = clock_ns
        self.ttl = TTLRefresher(self.retention.ttl_ns, self.retention.refresh_ns)

    async def publish_with_id(self, scope, identity, exclude, frame, event_id):
        envelope = new_envelope(self.node_id, scope, identity, exclude, frame,
                                event_id, clock_ns=self.clock_ns)
        key = stream_key(scope, identity)
        start = time.monotonic_ns()
        try:
            await asyncio.wait_for(self.client.xadd(
                key, redis_values(envelope), maxlen=self.retention.max_len,
                approximate=True), 2)
        except Exception as error:
            self.metrics.xadd_errors += 1
            self.metrics.last_error = str(error)
            log.warning('realtime/redis: XADD failed: %s', error)
            raise
        self.metrics.xadd_total += 1
        elapsed = time.monotonic_ns() - start
        self.metrics.last_xadd_lag_micros = elapsed // 1000
        if self.retention.enabled:
            try:
                # XADD and expiry share Go's single two-second deadline.
                await asyncio.wait_for(self.ttl.refresh_if_due(self.client, key),
                                       max(0, 2 - elapsed / 1_000_000_000))
            except Exception as error:
                self.metrics.retention_errors += 1
                self.metrics.last_error = str(error)
                log.warning('realtime/redis: PEXPIRE failed: %s', error)
