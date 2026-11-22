"""Own per-scope relay consumers and bind Hub first/last subscriptions.

Heartbeat, stream maintenance and top-level startup belong to the relay owner;
this component handles scope consumption and shares the publisher's TTL state.
All methods are called on the owning asyncio loop.
"""
import asyncio
from .relay_consumer import ScopeConsumer,ConsumerMetrics
from .relay_delivery import deliver_envelope


class RelayConsumers:
    def __init__(self, hub, publisher, *, read_client=None, daemon_runtime=None, wecom_outbound=None):
        self.hub = hub
        self.publisher = publisher
        self.read_client = read_client if read_client is not None else publisher.client
        self.daemon_runtime = daemon_runtime
        self.wecom_outbound = wecom_outbound
        self.metrics = ConsumerMetrics()
        self._consumers = {}
        self._tasks = set()
        self._failures = []
        self._parent = None
        self._watcher = None
        self._stopping = False

    def bind(self, parent_stop):
        if self._parent is not None:
            raise RuntimeError('Relay consumers already bound')
        self._parent = parent_stop
        self.hub.set_subscription_callbacks(self.start_scope, self.stop_scope)
        for scope, identity in self.hub.local_scopes():
            self.start_scope(scope, identity)
        self._watcher = asyncio.create_task(self._watch_parent())

    async def _watch_parent(self):
        await self._parent.wait()
        for stop in self._consumers.values():
            stop.set()

    async def _deliver(self, envelope):
        deliver_envelope(self.hub, envelope, daemon_runtime=self.daemon_runtime,
                         wecom_outbound=self.wecom_outbound)

    def start_scope(self, scope, identity):
        if self._stopping or self._parent is None or self._parent.is_set():
            return
        key = (scope, identity)
        if key in self._consumers:
            return
        stop = asyncio.Event()
        self._consumers[key] = stop
        consumer = ScopeConsumer(self.publisher.client, self.read_client,
                                 self.publisher.node_id, scope, identity, self._deliver,
                                 retention=self.publisher.retention, ttl=self.publisher.ttl,
                                 metrics=self.metrics)
        task = asyncio.create_task(consumer.run(stop))
        self._tasks.add(task)
        task.add_done_callback(self._done)

    def _done(self, task):
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            self._failures.append(task.exception())

    def stop_scope(self, scope, identity):
        stop = self._consumers.pop((scope, identity), None)
        if stop is not None:
            stop.set()

    def stop(self):
        self.hub.set_subscription_callbacks(None, None)
        self._stopping = True
        for stop in self._consumers.values():
            stop.set()
        if self._watcher is not None:
            self._watcher.cancel()

    async def wait(self):
        tasks = list(self._tasks)
        if self._watcher is not None:
            tasks.append(self._watcher)
        await asyncio.gather(*tasks, return_exceptions=True)
        if self._failures:
            raise ExceptionGroup('Relay consumer failures', list(self._failures))
