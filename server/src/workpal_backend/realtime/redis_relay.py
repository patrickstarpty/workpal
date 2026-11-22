"""Own the Python per-scope Redis relay and its background lifetimes.

The parent stop event owns maintenance shutdown. stop() prevents new consumers
and stops existing ones; callers set the parent event before awaiting wait().
Redis clients belong to the caller and are never closed by this component.
"""
import asyncio
import logging

from .relay_consumers import RelayConsumers
from .relay_ids import make_ulid
from .relay_maintenance import RelayMaintenance
from .relay_publisher import RelayPublisher

log = logging.getLogger(__name__)


class RedisRelay:
    def __init__(self, hub, write_client, *, read_client=None, retention=None,
                 node_id=None, daemon_runtime=None, wecom_outbound=None, metrics=None):
        self.node_id = make_ulid() if node_id is None else node_id
        self.metrics = metrics if metrics is not None else hub.metrics.redis
        self.publisher = RelayPublisher(write_client, self.node_id, retention=retention, metrics=self.metrics)
        self.consumers = RelayConsumers(hub, self.publisher, read_client=read_client,
                                       daemon_runtime=daemon_runtime, wecom_outbound=wecom_outbound)
        self.consumers.metrics = self.metrics
        self.maintenance = RelayMaintenance(hub, self.publisher, metrics=self.metrics)
        self._background = set()
        self._failures = []
        self._started = False

    async def start(self, parent_stop):
        if self._started:
            raise RuntimeError('Redis relay already started')
        self._started = True
        self.metrics.node_id = self.node_id
        try:
            await self._ping(self.publisher.client, parent_stop)
            if self.consumers.read_client is not self.publisher.client:
                await self._ping(self.consumers.read_client, parent_stop)
        except Exception as error:
            self.maintenance.metrics.connected = False
            self.maintenance.metrics.last_error = str(error)
            log.error('realtime/redis: initial ping failed: %s', error)
        else:
            self.maintenance.metrics.connected = True
        self.consumers.bind(parent_stop)
        for coroutine in (self.maintenance.heartbeat_loop(parent_stop),
                          self.maintenance.sweeper_loop(parent_stop)):
            task = asyncio.create_task(coroutine)
            self._background.add(task)
            task.add_done_callback(self._done)

    @staticmethod
    async def _ping(client, stop):
        if stop.is_set():
            raise RuntimeError('context canceled')
        pending = asyncio.create_task(client.ping())
        stopped = asyncio.create_task(stop.wait())
        try:
            done, _ = await asyncio.wait((pending, stopped), return_when=asyncio.FIRST_COMPLETED)
            if pending in done:
                return pending.result()
            raise RuntimeError('context canceled')
        finally:
            for task in (pending, stopped):
                if not task.done():
                    task.cancel()
            await asyncio.gather(pending, stopped, return_exceptions=True)

    def _done(self, task):
        self._background.discard(task)
        if not task.cancelled() and task.exception() is not None:
            self._failures.append(task.exception())

    def stop(self):
        self.consumers.stop()

    async def wait(self):
        results = await asyncio.gather(self.consumers.wait(), *list(self._background),
                                       return_exceptions=True)
        failures = list(self._failures)
        # Consumer ownership reports its own retained failures. Background
        # failures are retained by _done, including tasks already completed.
        if isinstance(results[0], Exception):
            failures.append(results[0])
        if failures:
            raise ExceptionGroup('Redis relay failures', failures)

    def set_daemon_runtime_deliverer(self, deliverer):
        self.consumers.daemon_runtime = deliverer

    def set_wecom_outbound_deliverer(self, deliverer):
        self.consumers.wecom_outbound = deliverer

    async def publish_with_id(self, scope, identity, exclude, frame, event_id):
        return await self.publisher.publish_with_id(scope, identity, exclude, frame, event_id)

    async def _publish(self, scope, identity, exclude, frame):
        try:
            await self.publisher.publish_with_id(scope, identity, exclude, frame, make_ulid())
        except Exception:
            # The broadcaster interface is fire-and-report; the publisher
            # records and logs errors, while publish_with_id remains fallible.
            pass

    async def broadcast_to_scope(self, scope, identity, frame):
        await self._publish(scope, identity, '', frame)

    async def broadcast_to_workspace(self, workspace_id, frame):
        await self._publish('workspace', workspace_id, '', frame)

    async def send_to_user(self, user_id, frame, *exclude_workspace):
        await self._publish('user', user_id, exclude_workspace[0] if exclude_workspace else '', frame)

    async def broadcast(self, frame):
        await self._publish('global', 'all', '', frame)
