"""Own fixed-shard readers, publishing and parent-controlled maintenance."""
import asyncio
import logging
import time

from .redis_relay import RedisRelay
from .relay_delivery import deliver_envelope
from .relay_envelope import heartbeat_key, _timestamp
from .relay_ids import make_ulid
from .relay_maintenance import _DeadlineClient, RelayMaintenance
from .relay_modes import _Broadcaster
from .sharded_maintenance import ShardedMaintenance
from .sharded_publisher import ShardedPublisher
from .sharded_reader import ShardReader

log = logging.getLogger(__name__)


class ShardedRelay(_Broadcaster):
    def __init__(self, hub, write_client, *, read_client=None, config=None,
                 node_id=None, metrics=None, daemon_runtime=None, wecom_outbound=None):
        self.hub = hub
        self.node_id = make_ulid() if node_id is None else node_id
        self.id_factory = make_ulid
        self.metrics = metrics if metrics is not None else hub.metrics.redis
        self.publisher = ShardedPublisher(write_client, self.node_id, config=config, metrics=self.metrics)
        self.maintenance = ShardedMaintenance(self.publisher)
        self.read_client = write_client if read_client is None else read_client
        self.daemon_runtime = daemon_runtime
        self.wecom_outbound = wecom_outbound
        self._stopping = False
        self._started = False
        self._tasks = []
        self.readers = [ShardReader(self.read_client, shard, self.publisher.config, self._deliver,
                                   metrics=self.metrics,
                                   generation=lambda shard=shard: self.maintenance.generations[shard],
                                   is_stopping=lambda: self._stopping)
                        for shard in range(self.publisher.config.shards)]

    def _deliver(self, envelope):
        deliver_envelope(self.hub, envelope, daemon_runtime=self.daemon_runtime,
                         wecom_outbound=self.wecom_outbound)

    def set_daemon_runtime_deliverer(self, deliverer):
        self.daemon_runtime = deliverer

    def set_wecom_outbound_deliverer(self, deliverer):
        self.wecom_outbound = deliverer

    async def publish_with_id(self, scope, identity, exclude, frame, event_id):
        return await self.publisher.publish_with_id(scope, identity, exclude, frame, event_id)

    _publish_id = publish_with_id

    async def start(self, parent_stop):
        if self._started:
            raise RuntimeError('Sharded Redis relay already started')
        self._started = True
        self.metrics.node_id = self.node_id
        try:
            await RedisRelay._ping(self.publisher.client, parent_stop)
            if self.read_client is not self.publisher.client:
                await RedisRelay._ping(self.read_client, parent_stop)
        except Exception as error:
            self.metrics.connected = False
            self.metrics.last_error = str(error)
            log.error('realtime/sharded-redis: initial ping failed: %s', error)
        else:
            self.metrics.connected = True
        self._tasks = [asyncio.create_task(self._heartbeat_loop(parent_stop)),
                       asyncio.create_task(self._retention_loop(parent_stop)),
                       *(asyncio.create_task(reader.run(parent_stop)) for reader in self.readers)]

    def stop(self):
        # Go Stop prevents another read but does not cancel an in-flight read
        # or the parent-owned maintenance loops.
        self._stopping = True

    async def wait(self):
        results = await asyncio.gather(*self._tasks, return_exceptions=True)
        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            raise ExceptionGroup('Sharded Redis relay failures', failures)

    async def heartbeat_once(self, stop=None):
        client = _DeadlineClient(self.publisher.client, stop)
        try:
            await client.set(heartbeat_key(self.node_id), _timestamp(time.time_ns()), ex=90)
        except Exception as error:
            self.metrics.connected = False
            self.metrics.last_error = str(error)
            return
        self.metrics.connected = True

    async def _heartbeat_loop(self, stop):
        await RelayMaintenance._periodic(self.heartbeat_once, 30, stop)

    async def _retention_loop(self, stop):
        # Sharded retention creates its ticker after the first pass.
        await self.maintenance.maintain_once(stop)
        period = self.publisher.config.maintenance_ns / 1_000_000_000
        loop = asyncio.get_running_loop()
        next_tick = loop.time() + period
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), max(0, next_tick - loop.time()))
                return
            except TimeoutError:
                pass
            now = loop.time()
            next_tick += max(1, int((now - next_tick) // period) + 1) * period
            await self.maintenance.maintain_once(stop)
