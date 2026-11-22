import asyncio


def test_shared_metrics_preserve_latest_error_across_relay_components():
    from workpal_backend.realtime.redis_relay import RedisRelay
    from workpal_backend.realtime.hub import Hub
    async def run():
        class Client:
            async def xadd(self,*args,**kwargs):
                raise RuntimeError('publish failure')
            async def set(self,*args,**kwargs):
                raise RuntimeError('heartbeat failure')
        hub = Hub()
        relay = RedisRelay(hub,Client())
        await relay.broadcast(b'event')
        assert relay.metrics.snapshot()['last_error'] == 'publish failure'
        await relay.maintenance.heartbeat_once()
        snapshot = relay.metrics.snapshot()
        assert snapshot['last_error'] == 'heartbeat failure'
        assert snapshot['xadd_errors'] == 1
        assert relay.publisher.metrics is relay.consumers.metrics is relay.maintenance.metrics
        await hub.close()
    asyncio.run(run())


def test_stream_observation_copy_mode_totals_and_reset_preserves_node_id():
    from workpal_backend.realtime.relay_metrics import RedisMetrics
    metrics = RedisMetrics()
    metrics.node_id = 'node'
    metrics.observe_stream('stream',2,-1)
    metrics.set_streams_without_ttl('legacy',2)
    metrics.set_streams_without_ttl('sharded',3)
    metrics.set_streams_without_ttl('legacy',1)
    snapshot = metrics.snapshot()
    assert snapshot['streams_without_ttl'] == 4
    snapshot['streams']['stream']['entries'] = 99
    assert metrics.snapshot()['streams']['stream']['entries'] == 2
    metrics.reset()
    snapshot = metrics.snapshot()
    assert snapshot['node_id'] == 'node'
    assert snapshot['streams'] == {} and snapshot['streams_without_ttl'] == 0
    assert snapshot['connected'] is False and snapshot['last_error'] == ''
