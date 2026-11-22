from workpal_backend.realtime.redis_client import RelayRedis as Redis
import asyncio


def test_start_pings_in_order_stop_retains_parent_maintenance_and_wait_joins():
    from workpal_backend.realtime.redis_relay import RedisRelay
    from workpal_backend.realtime.hub import Hub
    async def run():
        calls = []
        class Client:
            def __init__(self, name, fail=False):
                self.name, self.fail = name, fail
            async def ping(self):
                calls.append(self.name)
                if self.fail:
                    raise RuntimeError('ping failed')
            async def set(self, *args, **kwargs):
                await asyncio.Event().wait()
            async def scan(self, *args, **kwargs):
                return 0, []
        for failed, expected in [(False,['write','read']), (True,['write'])]:
            calls.clear()
            hub = Hub()
            relay = RedisRelay(hub, Client('write',failed), read_client=Client('read'), node_id='node')
            parent = asyncio.Event()
            await relay.start(parent)
            assert calls == expected
            assert relay.maintenance.metrics.connected is not failed
            relay.stop()
            assert not parent.is_set()
            parent.set()
            await asyncio.wait_for(relay.wait(), 1)
            assert not relay._background
            await hub.close()
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())


def test_broadcaster_uses_new_ids_and_first_exclusion_and_swallows_publish_errors():
    from workpal_backend.realtime.redis_relay import RedisRelay
    from workpal_backend.realtime.hub import Hub
    async def run():
        writes = []
        class Client:
            async def xadd(self, key, values, **kwargs):
                writes.append((key, values))
                raise RuntimeError('offline')
        hub = Hub()
        relay = RedisRelay(hub, Client())
        assert len(relay.node_id) == 26
        await relay.broadcast_to_scope('chat','c',b'one')
        await relay.broadcast_to_workspace('w',b'two')
        await relay.send_to_user('u',b'three','w1','w2')
        await relay.broadcast(b'four')
        assert [key for key,_ in writes] == ['ws:scope:chat:c:stream','ws:scope:workspace:w:stream','ws:scope:user:u:stream','ws:scope:global:all:stream']
        assert writes[2][1]['workspace_id'] == b'w1'
        assert len({values['event_id'] for _, values in writes}) == 4
        assert relay.publisher.metrics.xadd_errors == 4
        await hub.close()
    asyncio.run(run())


def test_real_redis_owner_start_publish_receive_heartbeat_and_shutdown(isolated_relay_redis_port):
    import json
    from uuid import uuid4
    import redis.asyncio as redis
    from workpal_backend.realtime.redis_relay import RedisRelay
    from workpal_backend.realtime.hub import Hub, Connection
    from workpal_backend.realtime.relay_envelope import stream_key, nodes_key, heartbeat_key
    async def run():
        # Restrict the legacy SCAN fixture to this test's owned streams; do not
        # maintain unrelated keys on the shared test Redis instance.
        scopes = set()
        class IsolatedClient(Redis):
            async def scan(self, cursor=0, **kwargs):
                return 0, [stream_key(*scope).encode() for scope in scopes]
        write = IsolatedClient(host='127.0.0.1', port=isolated_relay_redis_port)
        read = Redis(host='127.0.0.1', port=isolated_relay_redis_port)
        workspace, user = str(uuid4()), str(uuid4())
        frames = []
        class Socket:
            async def send_text(self, raw):
                frames.append(json.loads(raw))
            async def close(self, code):
                pass
        hub = Hub()
        hub.register(Connection(Socket(), lambda: None, workspace, user))
        scopes.update(hub.local_scopes())
        parent = asyncio.Event()
        relay = RedisRelay(hub, write, read_client=read)
        try:
            await relay.start(parent)
            async with asyncio.timeout(3):
                while True:
                    try:
                        groups = await write.xinfo_groups(stream_key('workspace',workspace))
                    except redis.ResponseError as error:
                        if 'no such key' not in str(error):
                            raise
                        groups = []
                    if any(group['name'] == ('node:' + relay.node_id).encode() for group in groups):
                        break
                    await asyncio.sleep(.01)
            await relay.broadcast_to_workspace(workspace,b'{"type":"owner-test"}')
            async with asyncio.timeout(3):
                while not frames:
                    await asyncio.sleep(.01)
            assert frames[0]['type'] == 'owner-test'
            assert len(frames[0]['event_id']) == 26
            assert 0 < await write.ttl(heartbeat_key(relay.node_id)) <= 90
            parent.set()
            relay.stop()
            await asyncio.wait_for(relay.wait(),7)
            assert not relay._background and not relay.consumers._tasks
        finally:
            parent.set()
            relay.stop()
            await relay.wait()
            await hub.close()
            await write.delete(heartbeat_key(relay.node_id), *[key for scope in scopes for key in (stream_key(*scope),nodes_key(*scope))])
            await write.aclose()
            await read.aclose()
    asyncio.run(run())
