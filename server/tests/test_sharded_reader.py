from workpal_backend.realtime.redis_client import RelayRedis as Redis
import asyncio
from workpal_backend.realtime.sharded_config import ShardedConfig
from workpal_backend.realtime.relay_metrics import RedisMetrics


def test_shard_reader_advances_invalid_messages_and_routes_only_complete_envelopes():
    from workpal_backend.realtime.sharded_reader import ShardReader
    async def run():
        calls=[];delivered=[];metrics=RedisMetrics()
        class Client:
            async def xread(self,streams,**options):
                calls.append((streams,options))
                return [(b'ws:relay:shard:2',[(b'1-0',{}),(b'2-0',{b'payload_json':b'no scope'}),
                         (b'3-0',{b'payload_json':b'frame',b'scope':b'workspace',b'scope_id':b'w'})])]
        reader=ShardReader(Client(),2,ShardedConfig().with_defaults(),delivered.append,metrics=metrics)
        reader.last_id='0-0'
        assert await reader.read_once(asyncio.Event()) is True
        assert reader.last_id=='3-0' and metrics.xread_total==3
        assert len(delivered)==1 and delivered[0].scope_id=='w'
        assert calls==[({'ws:relay:shard:2':'0-0'},{'count':128,'block':5000})]
    asyncio.run(run())


def test_generation_change_reanchors_replay_and_parent_cancel_joins_read():
    from workpal_backend.realtime.sharded_reader import ShardReader
    async def run():
        requested=asyncio.Queue();release=asyncio.Event();exited=asyncio.Event()
        generation=[0];now=[1_000_000_000_000];metrics=RedisMetrics()
        class Client:
            async def xread(self,streams,**options):
                await requested.put(dict(streams))
                try:
                    await release.wait()
                    release.clear()
                    return []
                finally:exited.set()
        stop=asyncio.Event()
        reader=ShardReader(Client(),0,ShardedConfig().with_defaults(),lambda event:None,
                           metrics=metrics,clock_ns=lambda:now[0],generation=lambda:generation[0])
        task=asyncio.create_task(reader.run(stop))
        assert await asyncio.wait_for(requested.get(),1)=={'ws:relay:shard:0':'700000-0'}
        now[0]+=60_000_000_000;generation[0]=1;release.set()
        assert await asyncio.wait_for(requested.get(),1)=={'ws:relay:shard:0':'760000-0'}
        exited.clear();stop.set();await asyncio.wait_for(task,1)
        assert exited.is_set() and metrics.xread_errors==0
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())


def test_read_error_backoff_is_cancelable_and_does_not_advance_cursor():
    from workpal_backend.realtime.sharded_reader import ShardReader
    async def run():
        entered=asyncio.Event();stop=asyncio.Event();metrics=RedisMetrics()
        class Client:
            async def xread(self,*args,**kwargs):
                entered.set()
                raise RuntimeError('read failed')
        reader=ShardReader(Client(),0,ShardedConfig().with_defaults(),lambda event:None,metrics=metrics)
        reader.last_id='123-4'
        task=asyncio.create_task(reader.read_once(stop))
        await entered.wait();await asyncio.sleep(0);stop.set()
        assert await asyncio.wait_for(task,1) is False
        assert reader.last_id=='123-4'
        assert metrics.xread_errors==1 and metrics.last_error=='read failed'
    asyncio.run(run())


def test_real_redis_replay_boundary_and_invalid_message_cursor(isolated_relay_redis_port):
    from uuid import uuid4
    from workpal_backend.realtime.sharded_reader import ShardReader
    from workpal_backend.realtime.sharded_config import sharded_stream_key
    async def run():
        client=Redis(host='127.0.0.1',port=isolated_relay_redis_port)
        shard=uuid4().int & ((1<<63)-1)
        key=sharded_stream_key(shard)
        delivered=[];metrics=RedisMetrics();stop=asyncio.Event();task=None
        reader=ShardReader(client,shard,ShardedConfig(read_block_ns=10_000_000).with_defaults(),
                           delivered.append,metrics=metrics,clock_ns=lambda:1_000_000_000_000)
        fields={'scope':'workspace','scope_id':'w','payload_json':'frame'}
        try:
            for identity in ['699999-0','700000-0','700000-1','900000-0']:
                await client.xadd(key,fields,id=identity)
            await client.xadd(key,{'payload_json':'invalid'},id='900001-0')
            task=asyncio.create_task(reader.run(stop))
            async with asyncio.timeout(3):
                while reader.last_id!='900001-0':await asyncio.sleep(.01)
            assert metrics.xread_total==3 and len(delivered)==2
            assert metrics.ack_total==0
            stop.set();await asyncio.wait_for(task,1)
            assert metrics.xread_errors==0
        finally:
            stop.set()
            if task is not None:await asyncio.wait_for(task,1)
            await client.delete(key);await client.aclose()
    asyncio.run(run())
