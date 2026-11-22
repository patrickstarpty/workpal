import asyncio
from types import SimpleNamespace

from workpal_backend.realtime.relay_publisher import RelayPublisher
from workpal_backend.realtime.stream_retention import RetentionConfig


class Client:
    def __init__(self):
        self.calls = []
        self.pages = [(7, [b'ws:scope:workspace:a:stream', b'legacy']), (0, [])]
        self.fail_set = False
        self.fail_expiry = False

    async def set(self, *args, **kwargs):
        self.calls.append(('set', args, kwargs))
        if self.fail_set:
            raise RuntimeError('offline')

    async def zadd(self, *args):
        self.calls.append(('zadd', args))
        raise RuntimeError('ignored node update')

    async def xtrim(self, *args, **kwargs):
        self.calls.append(('trim', args, kwargs))
        return 2

    async def pttl(self, key):
        return -1

    async def pexpire(self, *args):
        if self.fail_expiry:
            raise RuntimeError('expiry failed')
        return True

    async def zremrangebyscore(self, *args):
        self.calls.append(('prune', args))

    async def scan(self, *args, **kwargs):
        self.calls.append(('scan', args, kwargs))
        return self.pages.pop(0)


def test_heartbeat_failure_and_scope_score():
    from workpal_backend.realtime.relay_maintenance import RelayMaintenance
    async def run():
        client = Client()
        hub = SimpleNamespace(local_scopes=lambda: [('workspace', 'a')])
        maintenance = RelayMaintenance(hub, RelayPublisher(client, 'node'), clock_ns=lambda: 123_456_789_123)
        await maintenance.heartbeat_once()
        assert maintenance.metrics.connected
        assert client.calls == [('set', ('ws:node:node:heartbeat', '1970-01-01T00:02:03.456789123Z'), {'ex': 90}), ('zadd', ('ws:scope:workspace:a:nodes', {'node': 213.0}))]
        client.fail_set = True
        await maintenance.heartbeat_once()
        assert not maintenance.metrics.connected
        assert maintenance.metrics.last_error == 'offline'
        assert len(client.calls) == 3
    asyncio.run(run())


def test_sweep_deduplicates_local_keys_tracks_failed_ttl_and_prunes_completed_scan():
    from workpal_backend.realtime.relay_maintenance import RelayMaintenance
    async def run():
        client = Client()
        client.fail_expiry = True
        hub = SimpleNamespace(local_scopes=lambda: [('workspace', 'a')])
        publisher = RelayPublisher(client, 'node', retention=RetentionConfig(enabled=True))
        maintenance = RelayMaintenance(hub, publisher, clock_ns=lambda: 1000_123_456_789)
        await maintenance.sweep_once()
        assert maintenance.cursor == 7
        assert maintenance.without_ttl == {'ws:scope:workspace:a:stream', 'legacy'}
        assert maintenance.metrics.trimmed == 4
        assert maintenance.metrics.retention_errors == 2
        trims = [call for call in client.calls if call[0] == 'trim']
        assert all(call[2] == {'minid': '400123-0', 'approximate': False} for call in trims)
        assert ('prune', ('ws:scope:workspace:a:nodes', '-inf', '1000.000000')) in client.calls
        await maintenance.sweep_once()
        # The first completed scan includes both keys seen in its earlier page.
        assert maintenance.without_ttl == {'ws:scope:workspace:a:stream', 'legacy'}
        client.pages = [(0, [])]
        await maintenance.sweep_once()
        assert maintenance.without_ttl == {'ws:scope:workspace:a:stream'}
        assert maintenance.metrics.streams_without_ttl == 1
    asyncio.run(run())


def test_scan_failure_preserves_cursor_and_incomplete_scan_observations():
    from workpal_backend.realtime.relay_maintenance import RelayMaintenance
    async def run():
        client = Client()
        client.fail_expiry = True
        maintenance = RelayMaintenance(SimpleNamespace(local_scopes=lambda: []),
                                       RelayPublisher(client, 'node', retention=RetentionConfig(enabled=True)))
        await maintenance.sweep_once()
        assert maintenance.cursor == 7
        async def fail(*args, **kwargs):
            raise RuntimeError('scan failed')
        client.scan = fail
        await maintenance.sweep_once()
        assert maintenance.cursor == 7
        assert maintenance.without_ttl == {'ws:scope:workspace:a:stream', 'legacy'}
        assert maintenance.metrics.last_error == 'scan failed'
    asyncio.run(run())


def test_ttl_repair_preserves_observation_on_failed_write():
    from workpal_backend.realtime.stream_retention import TTLRefresher
    async def run():
        client = Client()
        client.fail_expiry = True
        refresher = TTLRefresher(900_000_000_000, 30_000_000_000)
        ttl, error = await refresher.reconcile_result(client, 'key', True)
        assert ttl == -1 and str(error) == 'expiry failed'
        async def pttl(key):
            return 300
        async def persist(key):
            raise RuntimeError('persist failed')
        client.pttl, client.persist = pttl, persist
        ttl, error = await refresher.reconcile_result(client, 'key', False)
        assert ttl == 300_000_000 and str(error) == 'persist failed'
    asyncio.run(run())


def test_periodic_maintenance_runs_immediately_and_parent_stop_joins_io():
    from workpal_backend.realtime.relay_maintenance import RelayMaintenance
    async def run():
        client = Client()
        entered = asyncio.Event()
        exited = asyncio.Event()
        async def pending(*args, **kwargs):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                exited.set()
        client.set = pending
        maintenance = RelayMaintenance(SimpleNamespace(local_scopes=lambda: []), RelayPublisher(client, 'node'))
        stop = asyncio.Event()
        task = asyncio.create_task(maintenance.heartbeat_loop(stop))
        await asyncio.wait_for(entered.wait(), 1)
        stop.set()
        await asyncio.wait_for(task, 1)
        assert exited.is_set()
        client.pages = [(0, [])]
        stop = asyncio.Event()
        scanned = asyncio.Event()
        async def scan(*args, **kwargs):
            scanned.set()
            return 0, []
        client.scan = scan
        task = asyncio.create_task(maintenance.sweeper_loop(stop))
        await asyncio.wait_for(scanned.wait(), 1)
        stop.set()
        await asyncio.wait_for(task, 1)
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())


def test_parent_cancellation_is_observed_as_redis_context_error():
    from workpal_backend.realtime.relay_maintenance import RelayMaintenance
    async def run():
        client = Client()
        entered = asyncio.Event()
        async def pending(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()
        client.set = pending
        maintenance = RelayMaintenance(SimpleNamespace(local_scopes=lambda: []), RelayPublisher(client,'node'))
        stop = asyncio.Event()
        task = asyncio.create_task(maintenance.heartbeat_loop(stop))
        await entered.wait()
        stop.set()
        await asyncio.wait_for(task,1)
        assert maintenance.metrics.last_error == 'context canceled'
        # Even an already-canceled Start context executes the initial pass,
        # whose Redis commands fail without being sent to the server.
        await maintenance.sweeper_loop(stop)
        assert maintenance.metrics.retention_errors == 1
        assert not any(call[0] == 'scan' for call in client.calls)
    asyncio.run(run())
