from workpal_backend.realtime.redis_client import RelayRedis as Redis
import asyncio,json
from uuid import uuid4
from workpal_backend.realtime.hub import Hub,Connection
from workpal_backend.realtime.relay_publisher import RelayPublisher
from workpal_backend.realtime.relay_envelope import stream_key,nodes_key


def test_real_redis_subscription_lifecycle_publish_delivery_dedup_and_stop(isolated_relay_redis_port):
    from workpal_backend.realtime.relay_consumers import RelayConsumers
    class Socket:
        def __init__(self):self.frames=[]
        async def send_text(self,raw):self.frames.append(json.loads(raw))
        async def close(self,code):pass
    async def run():
        write=Redis(host='127.0.0.1',port=isolated_relay_redis_port);read=Redis(host='127.0.0.1',port=isolated_relay_redis_port)
        w,x,u,v,chat,node=[str(uuid4()) for _ in range(6)]
        h=Hub();sockets=[];clients=[];parent=asyncio.Event()
        for workspace,user in [(w,u),(w,v),(x,u)]:
            s=Socket();c=Connection(s,lambda:None,workspace,user);h.register(c);sockets.append(s);clients.append(c)
        all_scopes=h.local_scopes()|{('chat',chat)}
        publisher=RelayPublisher(write,node);manager=RelayConsumers(h,publisher,read_client=read)
        async def eventually(check, timeout=3):
            async with asyncio.timeout(timeout):
                while not await check():await asyncio.sleep(.01)
        async def ready(scope,identity):return await write.zscore(nodes_key(scope,identity),node) is not None
        try:
            manager.bind(parent)
            await eventually(lambda:ready('workspace',w));await eventually(lambda:ready('user',u))
            for _ in range(2):await publisher.publish_with_id('workspace',w,'',b'{"type":"fixture"}','e')
            await publisher.publish_with_id('user',u,w,b'{"type":"personal"}','f')
            async def delivered():return manager.metrics.ack_total>=3 and all(len(s.frames)==1 for s in sockets)
            await eventually(delivered)
            assert sockets[0].frames==sockets[1].frames==[{'event_id':'e','type':'fixture'}]
            assert sockets[2].frames==[{'event_id':'f','type':'personal'}]
            h.subscribe(clients[0],'chat',chat);h.subscribe(clients[1],'chat',chat)
            await eventually(lambda:ready('chat',chat))
            h.unsubscribe(clients[0],'chat',chat)
            assert ('chat',chat) in manager._consumers
            h.unsubscribe(clients[1],'chat',chat)
            assert ('chat',chat) not in manager._consumers
            async def stopped():return await write.xinfo_consumers(stream_key('chat',chat),'node:'+node)==[]
            # Real Go Redis reads finish their 5s BLOCK before cleanup; the
            # isolated probe records that boundary instead of assuming <3s.
            await eventually(stopped, timeout=7)
            parent.set();manager.stop();await asyncio.wait_for(manager.wait(),7)
            assert not manager._tasks
            count=len(manager._consumers)
            manager.start_scope('chat',chat)
            assert len(manager._consumers)==count
        finally:
            parent.set();manager.stop();await manager.wait();await h.close()
            await write.delete(*[key for scope,identity in all_scopes for key in (stream_key(scope,identity),nodes_key(scope,identity))])
            await write.aclose();await read.aclose()
    asyncio.run(run())


def test_parent_cancellation_stops_consumers_without_explicit_stop():
    from workpal_backend.realtime.relay_consumers import RelayConsumers
    async def run():
        # Redis boundary waits indefinitely; parent cancellation must interrupt
        # the read and still execute consumer cleanup.
        entered=asyncio.Queue();cleaned=[]
        class Client:
            async def xgroup_create(self,*args,**kwargs):return True
            async def zadd(self,*args,**kwargs):return 1
            async def xreadgroup(self,group,node,streams,**kwargs):
                await entered.put(next(iter(streams)));await asyncio.Event().wait()
            async def xgroup_delconsumer(self,key,*args):cleaned.append(key);return 0
        class Socket:
            async def close(self,code):pass
        h=Hub();c=Connection(Socket(),lambda:None,'w','u');h.register(c)
        client=Client();manager=RelayConsumers(h,RelayPublisher(client,'n'));parent=asyncio.Event()
        manager.bind(parent)
        try:
            for _ in range(3):await asyncio.wait_for(entered.get(),1)
            parent.set();await asyncio.wait_for(manager.wait(),1)
            assert len(cleaned)==3 and not manager._tasks
            h.subscribe(c,'chat','after-cancel')
            assert ('chat','after-cancel') not in manager._consumers
        finally:manager.stop();await manager.wait();await h.close()
    asyncio.run(run())
