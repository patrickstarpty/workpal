import pytest


@pytest.mark.parametrize('mode',['legacy','dual','sharded'])
def test_factory_owns_correct_reader_pools_and_external_delivery_routes(mode):
    from workpal_backend.realtime.relay_factory import create_relay
    from workpal_backend.realtime.relay_modes import MirroredRelay, DualWriteBroadcaster
    from workpal_backend.realtime.redis_relay import RedisRelay
    from workpal_backend.realtime.sharded_relay import ShardedRelay
    from workpal_backend.realtime.sharded_config import ShardedConfig
    from workpal_backend.realtime.hub import Hub
    clients = {}
    def client(name):
        clients[name] = object()
        return clients[name]
    hub = Hub()
    daemon = lambda *args: None
    wecom = lambda *args: None
    bundle = create_relay(hub, client, mode=mode, config=ShardedConfig(),
                          daemon_runtime=daemon, wecom_outbound=wecom)
    assert isinstance(bundle.broadcaster, DualWriteBroadcaster)
    assert bundle.broadcaster.relay is bundle.relay
    if mode == 'dual':
        assert isinstance(bundle.relay, MirroredRelay)
        assert isinstance(bundle.relay.primary, ShardedRelay)
        assert isinstance(bundle.relay.mirror, RedisRelay)
        assert set(clients) == {'realtime-write','realtime-read-sharded','realtime-read-legacy'}
        assert bundle.relay.primary.publisher.client is bundle.relay.mirror.publisher.client
        assert bundle.relay.primary.read_client is clients['realtime-read-sharded']
        assert bundle.relay.mirror.consumers.read_client is clients['realtime-read-legacy']
        assert bundle.external_relay is bundle.relay.primary
    else:
        assert set(clients) == {'realtime-write','realtime-read'}
        assert isinstance(bundle.relay, RedisRelay if mode == 'legacy' else ShardedRelay)
    if mode == 'legacy':
        assert bundle.external_relay is None
        assert bundle.relay.consumers.daemon_runtime is None
    else:
        assert bundle.external_relay.daemon_runtime is daemon
        assert bundle.external_relay.wecom_outbound is wecom
    assert bundle.relay.metrics is hub.metrics.redis
