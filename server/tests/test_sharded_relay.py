import asyncio


def test_sharded_owner_stop_does_not_cancel_parent_maintenance_and_wait_joins():
    from workpal_backend.realtime.sharded_relay import ShardedRelay
    from workpal_backend.realtime.sharded_config import ShardedConfig
    from workpal_backend.realtime.hub import Hub

    async def run():
        calls = []
        reading = asyncio.Event()
        release = asyncio.Event()
        class Client:
            async def ping(self): calls.append('ping')
            async def set(self, *args, **kwargs): calls.append('heartbeat')
            async def exists(self, key): return 0
            async def info(self, section): return {}
            async def xread(self, streams, **kwargs):
                calls.append('read')
                reading.set()
                await release.wait()
                return []
        hub = Hub()
        client = Client()
        relay = ShardedRelay(hub, client, config=ShardedConfig(shards=1), node_id='n')
        parent = asyncio.Event()
        await relay.start(parent)
        await asyncio.wait_for(reading.wait(), 1)
        relay.stop()
        assert not parent.is_set()
        waiter = asyncio.create_task(relay.wait())
        release.set()
        await asyncio.sleep(.02)
        assert not waiter.done()
        assert calls.count('read') == 1
        assert calls[0] == 'ping'
        assert 'heartbeat' in calls
        parent.set()
        await asyncio.wait_for(waiter, 1)
        assert hub.metrics.redis.node_id == 'n'
        await hub.close()
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())


def test_real_sharded_publish_delivery_dedup_expiry_missing_generation_and_shutdown(isolated_relay_redis_port):
    from workpal_backend.realtime.redis_client import RelayRedis as Redis
    from workpal_backend.realtime.sharded_relay import ShardedRelay
    from workpal_backend.realtime.sharded_config import ShardedConfig, shard_for, sharded_stream_key
    from workpal_backend.realtime.hub import Hub, Connection
    from workpal_backend.realtime.relay_envelope import heartbeat_key
    import json

    async def run():
        write = Redis(host='127.0.0.1', port=isolated_relay_redis_port)
        read = Redis(host='127.0.0.1', port=isolated_relay_redis_port)
        frames = []
        class Socket:
            async def send_text(self, raw): frames.append(json.loads(raw))
            async def close(self, code): pass
        hub = Hub()
        hub.register(Connection(Socket(), lambda: None, 'w', 'u'))
        parent = asyncio.Event()
        relay = ShardedRelay(hub, write, read_client=read,
                             config=ShardedConfig(shards=2, enabled=True, read_block_ns=10_000_000))
        async def until(predicate):
            async with asyncio.timeout(3):
                while not predicate(): await asyncio.sleep(.01)
        try:
            await relay.start(parent)
            await relay.publish_with_id('workspace', 'w', '', b'{"type":"first"}', 'same')
            await relay.publish_with_id('workspace', 'w', '', b'{"type":"first"}', 'same')
            await until(lambda: relay.metrics.xread_total >= 2 and frames)
            assert frames == [{'type':'first','event_id':'same'}]
            shard = shard_for('workspace','w',2)
            key = sharded_stream_key(shard)
            assert 0 < await write.pttl(key) <= 900_000
            assert 0 < await write.ttl(heartbeat_key(relay.node_id)) <= 90
            await write.delete(key)
            await relay.maintenance.maintain_once()
            assert relay.maintenance.generations[shard] == 1
            assert relay.metrics.stream_missing_total == 1
            await relay.publish_with_id('workspace','w','',b'{"type":"second"}','new')
            await until(lambda: len(frames) == 2)
            assert frames[-1] == {'type':'second','event_id':'new'}
            assert relay.metrics.ack_total == 0
        finally:
            parent.set(); relay.stop()
            await asyncio.wait_for(relay.wait(),3)
            await hub.close()
            await write.aclose(); await read.aclose()
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())
