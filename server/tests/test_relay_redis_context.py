import asyncio
import pytest


def test_real_client_read_context_does_not_abort_inflight_result():
    from workpal_backend.realtime.redis_client import RelayRedis, read_with_context
    from workpal_backend.realtime.relay_consumer import _Stopped
    async def run():
        entered=asyncio.Event();release=asyncio.Event();stop=asyncio.Event()
        class Client(RelayRedis):
            async def xread(self, **kwargs):
                entered.set();await release.wait();return ['late result']
        client=Client()
        try:
            task=asyncio.create_task(read_with_context(client,'xread',stop,.01,streams={'key':'0-0'},block=100))
            await entered.wait();stop.set();await asyncio.sleep(.03)
            assert not task.done()
            release.set();assert await task==['late result']
            with pytest.raises(_Stopped):await read_with_context(client,'xread',stop,1,streams={'key':'0-0'})
        finally:await client.aclose()
    asyncio.run(run())


def test_blocking_read_uses_block_plus_ten_second_socket_budget():
    from workpal_backend.realtime.redis_client import RelayReadTimeout
    async def run():
        seen=[]
        class Connection:
            socket_timeout=3
            async def send_command(self,*args,**kwargs):seen.append(('write',self.socket_timeout))
            async def read_response(self,*args,**kwargs):seen.append(('read',self.socket_timeout));return []
        class Adapter(RelayReadTimeout,Connection):pass
        c=Adapter()
        await c.send_command('XREAD',b'BLOCK',5000,b'STREAMS','key','0-0')
        await c.read_response()
        assert seen==[('write',3),('read',15)]
        assert c.socket_timeout==3
        await c.send_command('XREAD','BLOCK',0,'STREAMS','key','0-0')
        await c.read_response()
        assert seen[-1]==('read',None)
    asyncio.run(run())


def test_scope_consumer_finishes_inflight_go_read_before_cleanup():
    from workpal_backend.realtime.redis_client import RelayRedis
    from workpal_backend.realtime.relay_consumer import ScopeConsumer
    async def run():
        entered=asyncio.Event();release=asyncio.Event();stop=asyncio.Event();delivered=[];cleaned=[]
        class Client(RelayRedis):
            async def xgroup_create(self,*args,**kwargs):return True
            async def zadd(self,*args,**kwargs):return 1
            async def xreadgroup(self,*args,**kwargs):
                entered.set();await release.wait()
                return [(b'key',[(b'1-0',{b'payload_json':b'late',b'scope':b'chat',b'scope_id':b'id'})])]
            async def xack(self,*args,**kwargs):return 1
            async def xgroup_delconsumer(self,*args,**kwargs):cleaned.append(True);return 0
        async def deliver(event):delivered.append(event.payload_json)
        client=Client();task=asyncio.create_task(ScopeConsumer(client,client,'node','chat','id',deliver).run(stop))
        try:
            await entered.wait();stop.set();await asyncio.sleep(.03)
            assert not task.done() and cleaned==[]
            release.set();await task
            assert delivered==[b'late'] and cleaned==[True]
        finally:
            release.set();await task;await client.aclose()
    asyncio.run(run())


def test_real_redis_read_finishes_its_block_after_logical_stop(isolated_relay_redis_port):
    from workpal_backend.realtime.redis_client import RelayRedis, read_with_context
    async def run():
        client=RelayRedis(host='127.0.0.1',port=isolated_relay_redis_port)
        control=RelayRedis(host='127.0.0.1',port=isolated_relay_redis_port)
        stop=asyncio.Event()
        try:
            await control.xgroup_create('read-budget','node',id='$',mkstream=True)
            task=asyncio.create_task(read_with_context(client,'xreadgroup',stop,1,'node','consumer',{'read-budget':'>'},block=100))
            async with asyncio.timeout(2):
                while not await control.xinfo_consumers('read-budget','node'):await asyncio.sleep(.001)
            stop.set()
            assert await asyncio.wait_for(task,1)==[]
            assert await control.ping()
        finally:
            await client.aclose();await control.aclose()
    asyncio.run(run())
