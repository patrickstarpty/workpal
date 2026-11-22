from workpal_backend.realtime.redis_client import RelayRedis as Redis
import asyncio
from uuid import uuid4
import pytest


def test_real_consumer_starts_at_tail_acknowledges_invalid_and_recovers_deleted_group(isolated_relay_redis_port):
    from workpal_backend.realtime.relay_consumer import ScopeConsumer
    from workpal_backend.realtime.relay_envelope import stream_key,nodes_key
    async def run():
        write=Redis(host='127.0.0.1',port=isolated_relay_redis_port)
        read=Redis(host='127.0.0.1',port=isolated_relay_redis_port)
        identity='test:'+uuid4().hex;node=uuid4().hex
        key=stream_key('chat',identity);registry=nodes_key('chat',identity)
        delivered=[];stop=asyncio.Event();task=None
        async def deliver(envelope):delivered.append(envelope)
        c=ScopeConsumer(write,read,node,'chat',identity,deliver)
        async def eventually(check):
            async with asyncio.timeout(3):
                while not await check():await asyncio.sleep(.01)
        try:
            await write.xadd(key,{'payload_json':'old'})
            task=asyncio.create_task(c.run(stop))
            async def ready():return await write.zscore(registry,node) is not None
            await eventually(ready)
            await write.xadd(key,{'payload_json':'new','event_id':'e'})
            await write.xadd(key,{'event_id':'invalid'})
            async def acked():return c.metrics.ack_total==2
            await eventually(acked)
            assert [(e.scope,e.scope_id,e.payload_json,e.event_id) for e in delivered]==[('chat',identity,b'new','e')]
            assert c.metrics.xread_total==2 and c.metrics.xread_errors==0
            assert (await write.xpending(key,'node:'+node))['pending']==0
            # Destroying the group retains entries. Recovery must start at 0-0.
            await write.xgroup_destroy(key,'node:'+node)
            async def recovered():return c.metrics.stream_missing_total==1 and c.metrics.ack_total>=5
            await eventually(recovered)
            assert [e.payload_json for e in delivered]==[b'new',b'old',b'new']
            stop.set();await asyncio.wait_for(task,7)
            assert await write.xinfo_consumers(key,'node:'+node)==[]
        finally:
            stop.set()
            if task and not task.done():await asyncio.wait_for(task,7)
            await write.delete(key,registry)
            await write.aclose();await read.aclose()
    asyncio.run(run())


def test_consumer_preserves_envelope_scope_and_acks_after_delivery_in_order():
    from workpal_backend.realtime.relay_consumer import ScopeConsumer
    from redis.exceptions import ResponseError
    async def run():
        stop=asyncio.Event();events=[]
        class Client:
            async def xgroup_create(self,*args,**kwargs):raise ResponseError('BUSYGROUP existing')
            async def zadd(self,*args,**kwargs):return 1
            async def xreadgroup(self,*args,**kwargs):
                assert kwargs==dict(count=32,block=5000)
                return [(b's',[(b'1-0',{b'payload_json':b'a',b'scope':b'user',b'scope_id':b'u'}),(b'2-0',{b'payload_json':b'b'})])]
            async def xack(self,stream,group,identity):
                events.append(('ack',identity));
                if identity==b'2-0':stop.set()
                return 1
            async def xgroup_delconsumer(self,*args):events.append(('clean',));return 0
        async def deliver(e):events.append(('deliver',e.scope,e.scope_id,e.payload_json))
        client=Client();c=ScopeConsumer(client,client,'n','chat','c',deliver)
        await asyncio.wait_for(c.run(stop),2)
        assert events==[('deliver','user','u',b'a'),('ack',b'1-0'),('deliver','chat','c',b'b'),('ack',b'2-0'),('clean',)]
        assert c.metrics.ack_total==2
    asyncio.run(run())
